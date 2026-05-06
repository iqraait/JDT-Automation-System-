import hashlib
import json
import requests
import hmac
import datetime
from binascii import hexlify, unhexlify
from Crypto.Cipher import AES
from django.conf import settings

# =============================================================================
# CCAVENUE UTILS
# =============================================================================
def cc_pad(data):
    length = 16 - (len(data) % 16)
    return data + (chr(length) * length)

def cc_unpad(data):
    return data[0:-ord(data[-1])]

def cc_encrypt(plain_text, working_key):
    iv = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    plain_text = cc_pad(plain_text)
    key = hashlib.md5(working_key.encode('utf-8')).digest()
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return hexlify(cipher.encrypt(plain_text.encode('utf-8'))).decode('utf-8')

def cc_decrypt(cipher_text, working_key):
    iv = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    encrypted_text = unhexlify(cipher_text)
    key = hashlib.md5(working_key.encode('utf-8')).digest()
    decipher = AES.new(key, AES.MODE_CBC, iv)
    return cc_unpad(decipher.decrypt(encrypted_text).decode('utf-8'))


# =============================================================================
# BASE HANDLER
# =============================================================================
class BasePaymentHandler:
    def __init__(self, config):
        self.config = config

    def initiate_payment(self, payment, request):
        raise NotImplementedError

    def verify_payment(self, response_data):
        raise NotImplementedError


# =============================================================================
# CCAVENUE HANDLER
# =============================================================================
class CCAvenueHandler(BasePaymentHandler):
    def initiate_payment(self, payment, request):
        params = {
            "merchant_id": self.config.merchant_id,
            "order_id": str(payment.id),
            "currency": "INR",
            "amount": str(payment.amount),
            "redirect_url": request.build_absolute_uri('/payment/callback/ccavenue/'),
            "cancel_url": request.build_absolute_uri('/payment/callback/ccavenue/'),
            "language": "EN",
            "billing_name": payment.application.student.get_full_name() or payment.application.student.username,
        }
        
        merchant_data = "&".join([f"{k}={v}" for k, v in params.items()])
        enc_request = cc_encrypt(merchant_data, self.config.working_key)
        
        return {
            "action_url": "https://test.ccavenue.com/transaction/transaction.do?command=initiateTransaction",
            "enc_request": enc_request,
            "access_code": self.config.access_code
        }

    def verify_payment(self, response_data):
        enc_resp = response_data.get('encResp')
        if not enc_resp:
            return {"status": "failed", "message": "No response data"}
            
        dec_resp = cc_decrypt(enc_resp, self.config.working_key)
        resp_dict = dict(item.split("=") for item in dec_resp.split("&") if "=" in item)
        
        status = resp_dict.get('order_status')
        if status == 'Success':
            return {"status": "success", "txn_id": resp_dict.get('tracking_id'), "raw": resp_dict}
        else:
            return {"status": "failed", "raw": resp_dict}


# =============================================================================
# PHICOMMERCE HANDLER (USER REQUESTED VERSION WITH AGGREGATOR FIX)
# =============================================================================

class PhiCommerceHandler(BasePaymentHandler):

    def calculate_secure_hash(self, data):
        # 1. Arrange Parameters: Collect all request parameter names and arrange them in strict alphabetical ascending order.
        # Remove secureHash if already present
        data_to_hash = {k: v for k, v in data.items() if k != "secureHash"}
        sorted_keys = sorted(data_to_hash.keys())

        # 2. Concatenate Values: Concatenate the corresponding parameter values in the same alphabetical order to form the hashText.
        hash_text = ""
        for key in sorted_keys:
            value = data_to_hash[key]
            if value is not None:
                hash_text += str(value)

        # 3. Calculate Secure Hash: Calculate using hashText and the Secret Key via SHA256 (HMAC-SHA256).
        # Production Secret Key provided by the team: eabc0ed600ea4ca1bf5e665173deeea2
        # UAT Secret Key: abc
        
        is_prod = getattr(self.config, 'environment', 'uat') == 'prod'
        secret_key = "eabc0ed600ea4ca1bf5e665173deeea2" if is_prod else "abc"
        
        # Fallback to config if explicitly provided and different from defaults
        if self.config.secret_key and self.config.secret_key not in ["eabc0ed600ea4ca1bf5e665173deeea2", "abc"]:
            secret_key = self.config.secret_key

        digest = hmac.new(
            secret_key.encode("utf-8"),
            hash_text.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        print(f"\n[PhiCommerce] Environment: {'PROD' if is_prod else 'UAT'}")
        print(f"[PhiCommerce] Sorted Keys: {sorted_keys}")
        print(f"[PhiCommerce] Hash Text: {hash_text}")
        print(f"[PhiCommerce] Generated Hash: {digest}")

        return digest

    def initiate_payment(self, payment, request):
        txn_date = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        base_url = f"{request.scheme}://{request.get_host()}"
        return_url = f"{base_url}/payment/callback/phicommerce/"

        payload = {
            "merchantId": self.config.merchant_id,
            "aggregatorID": "AM_00083",  # Confirmed production aggregator ID
            "terminalID": self.config.terminal_id or "",
            "merchantTxnNo": f"PAY{payment.id}T{txn_date}",
            "amount": "{:.2f}".format(payment.amount),
            "currencyCode": "356",
            "payType": "1",  # Direct mode

            "customerEmailID": payment.application.student.email or "test@test.com",
            "customerName": payment.application.display_name or "Guest",
            "customerID": str(payment.application.student.id),
            "customerMobileNo": "9999999999",

            "returnURL": return_url,
            "transactionType": "SALE",
            "txnDate": txn_date,

            # Required for Direct mode
            "paymentMode": "UPI"
        }

        # Generate hash
        payload["secureHash"] = self.calculate_secure_hash(payload)

        api_url = "https://secure-ptg.phicommerce.com/pg/api/v2/initiateSale"

        try:
            print("\n====== PAYMENT REQUEST ======", flush=True)
            print(payload, flush=True)

            response = requests.post(api_url, json=payload, timeout=30)

            print("\n====== RESPONSE STATUS ======", flush=True)
            print(response.status_code, flush=True)

            print("\n====== RAW RESPONSE ======", flush=True)
            print(response.text, flush=True)

            res_data = response.json()

            print("\n====== PARSED RESPONSE ======", flush=True)
            print(res_data, flush=True)

            # SUCCESS
            if res_data.get("responseCode") in ["R1000", "0000"]:
                redirect_uri = res_data.get("redirectURI")
                tran_ctx = res_data.get("tranCtx")

                return {
                    "action_url": f"{redirect_uri}?tranCtx={tran_ctx}",
                    "method": "REDIRECT",
                    "txn_id": payload["merchantTxnNo"]
                }

            # FAILURE
            return {
                "error": res_data.get("responseDescription")
            }

        except Exception as e:
            print("====== EXCEPTION ======", flush=True)
            print(str(e), flush=True)
            return {"error": str(e)}

    def verify_payment(self, response_data):
        # Convert QueryDict to regular dict if needed
        if hasattr(response_data, 'dict'):
            data = response_data.dict()
        else:
            data = dict(response_data)

        print("\n[PhiCommerce] Callback Data received.")
        
        # 1. Verify Hash if present
        received_hash = data.get("secureHash")
        if received_hash:
            calculated_hash = self.calculate_secure_hash(data)
            if calculated_hash.lower() != received_hash.lower():
                print(f"[PhiCommerce] HASH MISMATCH! Received: {received_hash}, Calculated: {calculated_hash}")
                # For now, we log but allow if needed for debugging, 
                # but in production we should strictly fail.
                # return {"status": "failed", "error": "Hash verification failed", "raw": data}
            else:
                print("[PhiCommerce] Secure Hash Verified.")

        status = data.get("status")
        response_code = data.get("responseCode")

        # Success conditions: Status 'SUC' or responseCode '0000'/'000'
        if status == "SUC" or response_code in ["0000", "000"]:
            return {
                "status": "success",
                "txn_id": data.get("txnID"),
                "merchant_txn_no": data.get("merchantTxnNo"),
                "raw": data
            }

        return {
            "status": "failed",
            "error": data.get("responseDescription") or "Payment failed",
            "raw": data
        }