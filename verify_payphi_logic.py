import os
import django
import hmac
import hashlib
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from applications.payment_handlers import PhiCommerceHandler
from applications.models import PaymentConfig

def test_phicommerce_hash():
    # Mock config
    config = PaymentConfig(
        secret_key="abc",
        merchant_id="https://qa.phicommerce.com/pg/api/merchant"
    )
    handler = PhiCommerceHandler(config)
    
    # Values from user example
    # Note: In the example, some keys might be empty. 
    # The hashText provided was: 
    # 100.00356asawari@phicommerce.com76765447712957934DR.AmbedkarT_7012054309698860https://qa.phicommerce.com/pg/api/merchantSALE20250828132505
    
    # We assigned them as:
    data = {
        "amount": "100.00",
        "currencyCode": "356",
        "customerEmailID": "asawari@phicommerce.com",
        "customerID": "76765447712957934",
        "customerMobileNo": "DR.Ambedkar",
        "customerName": "T_7012054309698860",
        "merchantId": "https://qa.phicommerce.com/pg/api/merchant",
        "merchantTxnNo": "SALE",
        "payType": "20250828132505",
        "returnURL": "",
        "transactionType": "",
        "txnDate": ""
    }
    
    # Wait, the user's example values mapping was actually:
    # returnURL: https://...
    # transactionType: SALE
    # txnDate: 2025...
    # Let's use the one that matches the hashText
    
    data_correct = {
        "amount": "100.00",
        "currencyCode": "356",
        "customerEmailID": "asawari@phicommerce.com",
        "customerID": "76765447712957934",
        "customerMobileNo": "DR.Ambedkar",
        "customerName": "T_7012054309698860",
        "merchantId": "",
        "merchantTxnNo": "",
        "payType": "",
        "returnURL": "https://qa.phicommerce.com/pg/api/merchant",
        "transactionType": "SALE",
        "txnDate": "20250828132505"
    }

    # As per user's logic in Python:
    # key = key_string.encode('utf-8')
    # msg_bytes = msg.encode('ascii')
    # mac = hmac.new(key, msg_bytes, hashlib.sha256)
    
    # 1. Arrange names alphabetically
    sorted_keys = sorted(data_correct.keys())
    # 2. Concat values
    hash_text = "".join(str(data_correct[k]) for k in sorted_keys if data_correct[k] != "")
    
    print(f"Generated hashText: {hash_text}")
    
    # 3. HMAC
    key = "abc".encode('utf-8')
    msg = hash_text.encode('ascii')
    expected_hash = "60eab1c0f9793fdc9a65a2a7eb52df66f33ede7abf53795865f45767700843ae"
    
    result = hmac.new(key, msg, hashlib.sha256).hexdigest()
    
    print(f"Result Hash: {result}")
    print(f"Expected:    {expected_hash}")
    print(f"Match:       {result == expected_hash}")

if __name__ == "__main__":
    test_phicommerce_hash()
