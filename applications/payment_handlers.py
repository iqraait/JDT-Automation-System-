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


import hashlib
import hmac
import datetime
import requests


class PhiCommerceHandler:

    def __init__(self, config):
        self.config = config

    # ============================================================
    # SECURE HASH
    # ============================================================
    def calculate_secure_hash(self, data):

        # Remove secureHash if exists
        data_to_hash = {
            k: v for k, v in data.items()
            if k != "secureHash"
        }

        # Sort keys alphabetically
        sorted_keys = sorted(data_to_hash.keys())

        hash_string = ""

        # Concatenate values
        for key in sorted_keys:
            value = data_to_hash[key]

            if value is not None and str(value) != "":
                hash_string += str(value)

        print("\n====== HASH STRING ======")
        print(hash_string)

        # ✅ PRODUCTION SECRET KEY
        secret_key = self.config.secret_key

        digest = hmac.new(
            secret_key.encode("utf-8"),
            hash_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        print("====== GENERATED HASH ======")
        print(digest)

        return digest

    # ============================================================
    # INITIATE PAYMENT
    # ============================================================
    def initiate_payment(self, payment, request):

        txn_date = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        base_url = f"{request.scheme}://{request.get_host()}"

        return_url = (
            f"{base_url}/payment/callback/phicommerce/"
        )

        payload = {

            "merchantId": self.config.merchant_id,

            # ✅ correct case
            "terminalId": self.config.terminal_id,

            "merchantTxnNo":
                f"PAY{payment.id}T{txn_date}",

            "amount":
                "{:.2f}".format(payment.amount),

            "currencyCode": "356",

            "payType": "1",

            "customerEmailID":
                payment.application.student.email,

            "customerName":
                payment.application.display_name,

            "customerID":
                str(payment.application.student.id),

            "customerMobileNo":
                "9999999999",

            "returnURL":
                return_url,

            "transactionType":
                "SALE",

            "txnDate":
                txn_date,

            # UPI / CARD / NB
            "paymentMode": "UPI",
        }

        # Generate secure hash
        payload["secureHash"] = (
            self.calculate_secure_hash(payload)
        )

        api_url = (
            "https://secure-ptg.phicommerce.com/"
            "pg/api/v2/initiateSale"
        )

        try:

            print("\n====== PAYMENT REQUEST ======")
            print(payload)

            response = requests.post(
                api_url,
                json=payload,
                timeout=30
            )

            print("\n====== RESPONSE STATUS ======")
            print(response.status_code)

            print("\n====== RAW RESPONSE ======")
            print(response.text)

            res_data = response.json()

            print("\n====== PARSED RESPONSE ======")
            print(res_data)

            # SUCCESS
            if res_data.get("responseCode") in [
                "R1000",
                "0000"
            ]:

                redirect_uri = (
                    res_data.get("redirectURI")
                )

                tran_ctx = (
                    res_data.get("tranCtx")
                )

                return {
                    "action_url":
                        f"{redirect_uri}?tranCtx={tran_ctx}",

                    "method": "REDIRECT",

                    "txn_id":
                        payload["merchantTxnNo"]
                }

            # FAILURE
            return {
                "error":
                    res_data.get(
                        "responseDescription"
                    )
            }

        except Exception as e:

            print("\n====== EXCEPTION ======")
            print(str(e))

            return {
                "error": str(e)
            }

    # ============================================================
    # VERIFY PAYMENT
    # ============================================================
    def verify_payment(self, response_data):

        print("\n====== CALLBACK RESPONSE ======")
        print(response_data)

        status = response_data.get("status")

        response_code = response_data.get(
            "responseCode"
        )

        if (
            status == "SUC"
            or response_code in ["0000", "000"]
        ):

            return {
                "status": "success",

                "txn_id":
                    response_data.get("txnID"),

                "merchant_txn_no":
                    response_data.get(
                        "merchantTxnNo"
                    ),

                "raw": response_data
            }

        return {
            "status": "failed",
            "raw": response_data
        }