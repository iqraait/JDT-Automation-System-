import hashlib
import json
import requests
import hmac
import datetime
from binascii import hexlify, unhexlify
from Crypto.Cipher import AES
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

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
        # Allow configuring dynamic custom callback URL
        callback_url = self.config.callback_url or request.build_absolute_uri('/payment/callback/ccavenue/')
        
        params = {
            "merchant_id": self.config.merchant_id,
            "order_id": str(payment.id),
            "currency": "INR",
            "amount": str(payment.amount),
            "redirect_url": callback_url,
            "cancel_url": callback_url,
            "language": "EN",
            "billing_name": payment.application.display_name or payment.application.student.username,
        }
        
        merchant_data = "&".join([f"{k}={v}" for k, v in params.items()])
        enc_request = cc_encrypt(merchant_data, self.config.working_key)
        
        # Dynamic base_url or fallback to environment selection
        if self.config.base_url:
            base_url = self.config.base_url.rstrip('/')
        elif self.config.environment == 'prod':
            base_url = "https://secure.ccavenue.com"
        else:
            base_url = "https://test.ccavenue.com"
            
        action_url = f"{base_url}/transaction/transaction.do?command=initiateTransaction"
        
        return {
            "action_url": action_url,
            "enc_request": enc_request,
            "access_code": self.config.access_code
        }

    def verify_payment(self, response_data):
        if hasattr(response_data, 'dict'):
            response_data = response_data.dict()
            
        enc_resp = response_data.get('encResp') or response_data.get('encresp')
        if not enc_resp:
            logger.error("CCAvenue verify_payment: No encResp in response data")
            return {"status": "failed", "message": "No response data"}
            
        enc_resp = enc_resp.strip()
        try:
            dec_resp = cc_decrypt(enc_resp, self.config.working_key)
            resp_dict = {}
            for item in dec_resp.split("&"):
                if "=" in item:
                    parts = item.split("=", 1)
                    resp_dict[parts[0]] = parts[1]
        except Exception as e:
            logger.exception("CCAvenue decryption or parsing failed")
            return {"status": "failed", "message": f"Decryption failed: {str(e)}"}
        
        status = resp_dict.get('order_status')
        if status and status.strip().lower() == 'success':
            return {
                "status": "success", 
                "txn_id": resp_dict.get('tracking_id'), 
                "payment_mode": resp_dict.get('payment_mode'),
                "raw": resp_dict
            }
        else:
            return {"status": "failed", "raw": resp_dict}


import hashlib
import hmac
import datetime
import requests


# =============================================================================
# PHICOMMERCE HANDLER
# =============================================================================
class PhiCommerceHandler(BasePaymentHandler):
    """
    PhiCommerce V2 payment handler.

    Hash algorithm (from PhiCommerce official docs — Java / Python / .NET samples):
      1. Collect all request fields EXCEPT secureHash
      2. Sort field names alphabetically (A-Z)
      3. Skip fields whose value is None or empty string ""
      4. Concatenate the VALUES only — NO separator between them
      5. Encode the resulting string as ASCII bytes
      6. Compute HMAC-SHA256 using the secret key (UTF-8 encoded)
      7. Return the hex digest (lowercase)

    Example (from PhiCommerce docs):
      Fields sorted: amount=150.00, currencyCode=356, customerEmailID=..., ...
      Hash string  : "150.00356TEST@phicommerce.com..."   ← values only, no delimiter
    """

    def _build_hash_string(self, data):
        """
        Sort keys A-Z, exclude secureHash, skip None/empty values,
        concatenate remaining values with NO separator.
        """
        sorted_keys = sorted(k for k in data if k != "secureHash")
        return "".join(
            str(data[k])
            for k in sorted_keys
            if data[k] is not None and str(data[k]).strip() != ""
        )

    def calculate_secure_hash(self, data):
        """
        HMAC-SHA256: key encoded as UTF-8, message encoded as ASCII.
        Matches PhiCommerce's Java (msg.getBytes("ASCII")), Python (msg.encode('ascii')),
        and .NET (Encoding.ASCII.GetBytes(msg)) reference implementations.
        """
        hash_string = self._build_hash_string(data)
        secret_key = self.config.secret_key or ""

        logger.debug("PhiCommerce hash input: %s", hash_string)

        digest = hmac.new(
            secret_key.encode("utf-8"),
            hash_string.encode("ascii"),
            hashlib.sha256
        ).hexdigest()

        logger.debug("PhiCommerce computed hash: %s", digest)
        return digest

    def verify_response_hash(self, response_data):
        """Verify the secureHash that PhiCommerce sends in callback / webhook responses."""
        received_hash = response_data.get("secureHash", "")
        if not received_hash:
            logger.warning("PhiCommerce: no secureHash in response — skipping verification")
            return True

        computed = self.calculate_secure_hash(dict(response_data))
        if computed.lower() != received_hash.lower():
            logger.error(
                "PhiCommerce response hash MISMATCH — received: %s  computed: %s",
                received_hash, computed
            )
            return False
        return True

    def initiate_payment(self, payment, request):
        import datetime

        txn_date = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        merchant_txn_no = f"PAY{payment.id}T{txn_date}"

        # ── Build payload ────────────────────────────────────────────────────
        # payType=0 → standard redirect; customer selects payment method on the
        # PhiCommerce-hosted page (no paymentMode / paymentOptionCodes needed).
        payload = {
            "merchantId":        self.config.merchant_id,
            "merchantTxnNo":     merchant_txn_no,
            "aggregatorID":      self.config.aggregator_id,
            "amount":            "{:.2f}".format(payment.amount),
            "currencyCode":      "356",
            "payType":           "0",
            "customerEmailID":   payment.application.student.email or "guest@phicommerce.com",
            "transactionType":   "SALE",
            "txnDate":           txn_date,
            "customerName":      payment.application.display_name,
            "customerID":        str(payment.application.student.id),
            "customerMobileNo":  "9999999999",
            "returnURL":         request.build_absolute_uri('/payment/callback/phicommerce/'),
        }
        if self.config.terminal_id:
            payload["terminalId"] = self.config.terminal_id
        # ── Compute and attach secure hash ───────────────────────────────────
        payload["secureHash"] = self.calculate_secure_hash(payload)
        
        print("\n====== GENERATED HASH ======", flush=True)
        print(payload["secureHash"], flush=True)
        
        print("\n====== PAYMENT REQUEST ======", flush=True)
        print(payload, flush=True)

        # ── API URL ──────────────────────────────────────────────────────────
        # Use base_url from config if available, otherwise default to production
        base_url = self.config.base_url or "https://secure-ptg.phicommerce.com"
        # Ensure no trailing slash on base_url for consistent joining
        base_url = base_url.rstrip("/")
        api_url = f"{base_url}/pg/api/v2/initiateSale"

        logger.info(
            "PhiCommerce initiateSale → merchantTxnNo=%s  amount=%s",
            merchant_txn_no, payload["amount"]
        )

        try:
            response = requests.post(api_url, json=payload, timeout=30)
            
            print("\n====== RESPONSE STATUS ======", flush=True)
            print(response.status_code, flush=True)
            
            print("\n====== RAW RESPONSE ======", flush=True)
            print(response.text, flush=True)

            try:
                res_data = response.json()
                print("\n====== PARSED RESPONSE ======", flush=True)
                print(res_data, flush=True)
            except ValueError:
                logger.error(
                    "PhiCommerce non-JSON response (HTTP %s): %s",
                    response.status_code, response.text[:500]
                )
                return {"error": f"Invalid JSON response (HTTP {response.status_code})"}

            logger.info("PhiCommerce API response: %s", res_data)

            # ── Success: gateway accepted the request ─────────────────────
            if res_data.get("responseCode") in ("R1000", "0000"):
                redirect_uri = res_data.get("redirectURI")
                tran_ctx    = res_data.get("tranCtx")

                if redirect_uri and tran_ctx:
                    return {
                        "action_url":      f"{redirect_uri}?tranCtx={tran_ctx}",
                        "method":          "REDIRECT",
                        "merchant_txn_no": merchant_txn_no,
                        "tran_ctx":        tran_ctx,
                    }

                logger.error("PhiCommerce missing redirectURI/tranCtx in success response: %s", res_data)
                return {"error": "Missing redirectURI or tranCtx in gateway response"}

            # ── Failure ─────────────
            error_msg = (
                res_data.get("responseDescription")
                or res_data.get("respDescription")
                or res_data.get("message")
                or "Payment initiation failed"
            )
            logger.error("PhiCommerce initiateSale rejected: %s | response: %s", error_msg, res_data)
            return {"error": error_msg}

        except requests.exceptions.Timeout:
            logger.error("PhiCommerce request timed out")
            return {"error": "Payment gateway timeout. Please try again."}

        except requests.exceptions.ConnectionError:
            logger.error("PhiCommerce connection error")
            return {"error": "Unable to connect to payment gateway."}

        except Exception as e:
            logger.exception("Unexpected error in PhiCommerce initiate_payment")
            return {"error": f"Unexpected error: {str(e)}"}

    def verify_payment(self, response_data):
        """
        Verify the callback / webhook response sent by PhiCommerce to returnURL.

        PhiCommerce posts these fields (among others):
          merchantTxnNo  — our original transaction reference
          txnID          — bank / gateway transaction ID
          status         — SUC (success) or FAI (failure)
          responseCode   — 0000 for success
          secureHash     — HMAC of the response fields (use 'abc' key)
        """
        # QueryDict → plain dict (Django POST data)
        if hasattr(response_data, 'dict'):
            response_data = response_data.dict()

        logger.info("PhiCommerce verify_payment received: %s", response_data)

        # ── Hash verification ─────────────────────────────────────────────
        if not self.verify_response_hash(response_data):
            return {
                "status": "failed",
                "error": "Secure hash verification failed",
                "raw": response_data,
            }

        status           = (response_data.get("status") or response_data.get("txnStatus") or "").upper()
        resp_code        = response_data.get("responseCode", "")
        merchant_txn_no  = response_data.get("merchantTxnNo", "")

        # ── Also check inside responseParams (nested success response) ────
        resp_params = response_data.get("responseParams", {})
        if isinstance(resp_params, dict):
            if not merchant_txn_no:
                merchant_txn_no = resp_params.get("merchantTxnNo", "")
            if not resp_code:
                resp_code = resp_params.get("responseCode", "")

        txn_id = (
            response_data.get("txnID")
            or resp_params.get("txnID")
            or response_data.get("bankTxnID")
            or ""
        )

        if status in ("SUC", "SUCCESS") or resp_code == "0000":
            logger.info(
                "PhiCommerce payment SUCCESS — merchantTxnNo=%s  txnID=%s",
                merchant_txn_no, txn_id
            )
            return {
                "status":          "success",
                "merchant_txn_no": merchant_txn_no,
                "txn_id":          txn_id,
                "payment_mode":    response_data.get("paymentMode") or resp_params.get("paymentMode"),
                "raw":             response_data,
            }

        logger.warning(
            "PhiCommerce payment FAILED — merchantTxnNo=%s  status=%s  responseCode=%s",
            merchant_txn_no, status, resp_code
        )
        return {
            "status":          "failed",
            "merchant_txn_no": merchant_txn_no,
            "error": (
                response_data.get("responseDescription")
                or response_data.get("respDescription")
                or resp_params.get("respDescription")
                or "Payment failed"
            ),
            "raw": response_data,
        }
