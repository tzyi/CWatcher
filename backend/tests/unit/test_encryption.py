"""
加密工具單元測試

測試 AES-256-GCM 加密和解密功能
"""

import pytest
import base64
import os
from unittest.mock import patch

from app.utils.encryption import (
    AESGCMEncryption, EncryptionError,
    encryption, encrypt_text, decrypt_text, verify_encryption
)


class TestAESGCMEncryption:
    """測試 AES-GCM 加密類別"""
    
    def setup_method(self):
        """測試前設置"""
        self.encryption = AESGCMEncryption()
    
    def test_encryption_initialization_default(self):
        """測試預設初始化"""
        enc = AESGCMEncryption()
        assert enc.master_key is not None
        assert enc._derived_key is not None
        assert len(enc._derived_key) == 32
    
    def test_encryption_initialization_custom_key(self):
        """測試自定義密鑰初始化"""
        custom_key = "my-custom-master-key-for-testing-purposes"
        enc = AESGCMEncryption(master_key=custom_key)
        assert enc.master_key == custom_key
        assert len(enc._derived_key) == 32
    
    def test_derive_key_consistent(self):
        """測試密鑰派生的一致性"""
        password = "test-password"
        
        # 使用相同密碼多次派生應該得到相同結果
        key1 = self.encryption._derive_key(password)
        key2 = self.encryption._derive_key(password)
        
        assert key1 == key2
        assert len(key1) == 32
    
    def test_encrypt_basic(self):
        """測試基本加密功能"""
        plaintext = "Hello, World!"
        encrypted = self.encryption.encrypt(plaintext)
        
        assert encrypted != plaintext
        assert len(encrypted) > 0
        assert isinstance(encrypted, str)
        
        # 驗證是 Base64 編碼
        try:
            base64.b64decode(encrypted.encode())
        except Exception:
            pytest.fail("加密結果不是有效的 Base64 編碼")
    
    def test_encrypt_empty_string(self):
        """測試加密空字串失敗"""
        with pytest.raises(EncryptionError) as exc_info:
            self.encryption.encrypt("")
        
        assert "明文不能為空" in str(exc_info.value)
    
    def test_encrypt_none(self):
        """測試加密 None 失敗"""
        with pytest.raises(EncryptionError) as exc_info:
            self.encryption.encrypt(None)
        
        assert "明文不能為空" in str(exc_info.value)
    
    def test_decrypt_basic(self):
        """測試基本解密功能"""
        plaintext = "Test decryption message"
        encrypted = self.encryption.encrypt(plaintext)
        decrypted = self.encryption.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_decrypt_empty_string(self):
        """測試解密空字串失敗"""
        with pytest.raises(EncryptionError) as exc_info:
            self.encryption.decrypt("")
        
        assert "加密資料不能為空" in str(exc_info.value)
    
    def test_decrypt_invalid_base64(self):
        """測試解密無效 Base64 失敗"""
        with pytest.raises(EncryptionError) as exc_info:
            self.encryption.decrypt("invalid-base64-data!")
        
        assert "解密失敗" in str(exc_info.value)
    
    def test_decrypt_too_short(self):
        """測試解密過短資料失敗"""
        # 建立一個太短的有效 Base64 字串
        short_data = base64.b64encode(b"short").decode()
        
        with pytest.raises(EncryptionError) as exc_info:
            self.encryption.decrypt(short_data)
        
        assert "加密資料格式錯誤" in str(exc_info.value)
    
    def test_decrypt_corrupted_data(self):
        """測試解密損壞資料失敗"""
        # 建立一個看起來有效但實際損壞的加密資料
        fake_nonce = b"123456789012"  # 12 bytes nonce
        fake_ciphertext = b"fake_encrypted_data"
        corrupted_data = base64.b64encode(fake_nonce + fake_ciphertext).decode()
        
        with pytest.raises(EncryptionError) as exc_info:
            self.encryption.decrypt(corrupted_data)
        
        assert "解密失敗" in str(exc_info.value)
    
    def test_encrypt_decrypt_roundtrip(self):
        """測試加密解密往返"""
        test_cases = [
            "Simple text",
            "包含中文的文本",
            "Text with special chars: !@#$%^&*()",
            "Multi\nline\ntext\nwith\nbreaks",
            "Very long text " * 100,
            "12345",
            "a",
            " ",  # 單個空格
        ]
        
        for plaintext in test_cases:
            encrypted = self.encryption.encrypt(plaintext)
            decrypted = self.encryption.decrypt(encrypted)
            assert decrypted == plaintext, f"往返失敗: {plaintext}"
    
    def test_encrypt_different_results(self):
        """測試相同明文產生不同密文"""
        plaintext = "Same message"
        
        encrypted1 = self.encryption.encrypt(plaintext)
        encrypted2 = self.encryption.encrypt(plaintext)
        
        # 由於使用隨機 nonce，相同明文應該產生不同密文
        assert encrypted1 != encrypted2
        
        # 但解密後應該都是原始明文
        assert self.encryption.decrypt(encrypted1) == plaintext
        assert self.encryption.decrypt(encrypted2) == plaintext
    
    def test_encrypt_credentials(self):
        """測試加密憑證"""
        username = "admin"
        password = "secure-password-123"
        
        encrypted_username, encrypted_password = self.encryption.encrypt_credentials(
            username, password
        )
        
        assert encrypted_username != username
        assert encrypted_password != password
        
        # 驗證可以正確解密
        decrypted_username, decrypted_password = self.encryption.decrypt_credentials(
            encrypted_username, encrypted_password
        )
        
        assert decrypted_username == username
        assert decrypted_password == password
    
    def test_different_keys_different_results(self):
        """測試不同密鑰產生不同結果"""
        plaintext = "Test message"
        
        enc1 = AESGCMEncryption(master_key="key1")
        enc2 = AESGCMEncryption(master_key="key2")
        
        encrypted1 = enc1.encrypt(plaintext)
        encrypted2 = enc2.encrypt(plaintext)
        
        # 不同密鑰應該產生不同密文
        assert encrypted1 != encrypted2
        
        # 用錯誤密鑰解密應該失敗
        with pytest.raises(EncryptionError):
            enc1.decrypt(encrypted2)
        
        with pytest.raises(EncryptionError):
            enc2.decrypt(encrypted1)


class TestEncryptionHelpers:
    """測試加密便利函數"""
    
    def test_encrypt_text(self):
        """測試加密文本便利函數"""
        plaintext = "Test encryption helper"
        encrypted = encrypt_text(plaintext)
        
        assert encrypted != plaintext
        assert len(encrypted) > 0
    
    def test_decrypt_text(self):
        """測試解密文本便利函數"""
        plaintext = "Test decryption helper"
        encrypted = encrypt_text(plaintext)
        decrypted = decrypt_text(encrypted)
        
        assert decrypted == plaintext
    
    def test_encrypt_decrypt_text_roundtrip(self):
        """測試便利函數往返"""
        test_messages = [
            "Simple message",
            "包含中文",
            "Special chars: !@#$%^&*()",
            "12345",
            "a"
        ]
        
        for message in test_messages:
            encrypted = encrypt_text(message)
            decrypted = decrypt_text(encrypted)
            assert decrypted == message
    
    def test_verify_encryption_success(self):
        """測試驗證加密功能成功"""
        assert verify_encryption() is True
    
    @patch('app.utils.encryption.encrypt_text')
    def test_verify_encryption_failure(self, mock_encrypt):
        """測試驗證加密功能失敗"""
        mock_encrypt.side_effect = Exception("加密失敗")
        
        assert verify_encryption() is False


class TestEncryptionIntegration:
    """測試加密功能整合"""
    
    def test_global_encryption_instance(self):
        """測試全域加密實例"""
        assert encryption is not None
        assert hasattr(encryption, 'encrypt')
        assert hasattr(encryption, 'decrypt')
    
    def test_environment_variable_integration(self):
        """測試環境變數整合"""
        test_key = "test-environment-key-123"
        
        with patch.dict(os.environ, {'CWATCHER_MASTER_KEY': test_key}):
            enc = AESGCMEncryption()
            assert enc.master_key == test_key
    
    def test_concurrent_encryption(self):
        """測試並發加密（模擬多線程環境）"""
        import threading
        import time
        
        results = []
        errors = []
        
        def encrypt_worker(text, worker_id):
            try:
                encrypted = encryption.encrypt(f"{text}-{worker_id}")
                decrypted = encryption.decrypt(encrypted)
                results.append((worker_id, decrypted))
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # 建立多個線程進行並發加密
        threads = []
        for i in range(10):
            thread = threading.Thread(
                target=encrypt_worker,
                args=("concurrent-test", i)
            )
            threads.append(thread)
            thread.start()
        
        # 等待所有線程完成
        for thread in threads:
            thread.join()
        
        # 驗證結果
        assert len(errors) == 0, f"並發加密錯誤: {errors}"
        assert len(results) == 10
        
        # 驗證每個結果都正確
        for worker_id, decrypted in results:
            expected = f"concurrent-test-{worker_id}"
            assert decrypted == expected
    
    def test_large_data_encryption(self):
        """測試大數據量加密"""
        # 測試較大的文本（1MB）
        large_text = "A" * (1024 * 1024)
        
        encrypted = encryption.encrypt(large_text)
        decrypted = encryption.decrypt(encrypted)
        
        assert decrypted == large_text
        assert len(encrypted) > len(large_text)  # 加密後應該更長（Base64 編碼）
    
    def test_unicode_text_encryption(self):
        """測試 Unicode 文本加密"""
        unicode_texts = [
            "Hello, 世界!",
            "Привет, мир!",
            "مرحبا بالعالم",
            "🚀🔐💻🌍",
            "Ωαξοσχώςουροσιαάπι"
        ]
        
        for text in unicode_texts:
            encrypted = encryption.encrypt(text)
            decrypted = encryption.decrypt(encrypted)
            assert decrypted == text, f"Unicode 測試失敗: {text}"
    
    def test_encryption_deterministic_with_fixed_nonce(self):
        """測試加密的隨機性"""
        plaintext = "Test randomness"
        
        # 連續加密相同文本應該產生不同結果
        results = []
        for _ in range(5):
            encrypted = encryption.encrypt(plaintext)
            results.append(encrypted)
        
        # 所有結果應該不同（因為使用隨機 nonce）
        unique_results = set(results)
        assert len(unique_results) == len(results), "加密結果不夠隨機"
        
        # 但所有結果解密後應該相同
        for encrypted in results:
            decrypted = encryption.decrypt(encrypted)
            assert decrypted == plaintext


class TestEncryptionErrorHandling:
    """測試加密錯誤處理"""
    
    def setup_method(self):
        """測試前設置"""
        self.encryption = AESGCMEncryption()
    
    def test_encryption_error_inheritance(self):
        """測試加密錯誤繼承"""
        assert issubclass(EncryptionError, Exception)
    
    def test_error_messages_localized(self):
        """測試錯誤訊息本地化"""
        try:
            self.encryption.encrypt("")
        except EncryptionError as e:
            assert "明文" in str(e)  # 中文錯誤訊息
        
        try:
            self.encryption.decrypt("")
        except EncryptionError as e:
            assert "加密資料" in str(e)  # 中文錯誤訊息
    
    @patch('app.utils.encryption.AESGCM')
    def test_encrypt_aesgcm_failure(self, mock_aesgcm_class):
        """測試 AESGCM 加密失敗"""
        mock_aesgcm = mock_aesgcm_class.return_value
        mock_aesgcm.encrypt.side_effect = Exception("AESGCM 加密失敗")
        
        with pytest.raises(EncryptionError) as exc_info:
            self.encryption.encrypt("test")
        
        assert "加密失敗" in str(exc_info.value)
    
    @patch('app.utils.encryption.AESGCM')
    def test_decrypt_aesgcm_failure(self, mock_aesgcm_class):
        """測試 AESGCM 解密失敗"""
        # 先正常加密一個值
        plaintext = "test"
        encrypted = self.encryption.encrypt(plaintext)
        
        # 然後模擬解密失敗
        mock_aesgcm = mock_aesgcm_class.return_value
        mock_aesgcm.decrypt.side_effect = Exception("AESGCM 解密失敗")
        
        with pytest.raises(EncryptionError) as exc_info:
            self.encryption.decrypt(encrypted)
        
        assert "解密失敗" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])