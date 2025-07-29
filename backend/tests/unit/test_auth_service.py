"""
認證服務單元測試

測試 SSH 憑證加密、解密、驗證和管理功能
"""

import pytest
from unittest.mock import Mock, patch
import io

from app.services.auth_service import (
    AuthService, AuthenticationError, KeyValidationError, 
    SSHKeyType
)
from app.utils.encryption import AESGCMEncryption, EncryptionError


class TestAuthService:
    """測試認證服務"""
    
    def setup_method(self):
        """測試前設置"""
        self.encryption = AESGCMEncryption()
        self.auth_service = AuthService(encryption=self.encryption)
    
    def test_service_initialization(self):
        """測試服務初始化"""
        assert self.auth_service.encryption is not None
        assert len(self.auth_service.key_types) == 4
        assert SSHKeyType.RSA in self.auth_service.key_types
    
    def test_encrypt_password_success(self):
        """測試密碼加密成功"""
        password = "SecurePassword123!"
        encrypted = self.auth_service.encrypt_password(password)
        
        assert encrypted != password
        assert len(encrypted) > 0
        
        # 驗證可以解密
        decrypted = self.auth_service.decrypt_password(encrypted)
        assert decrypted == password
    
    def test_encrypt_password_empty(self):
        """測試空密碼加密失敗"""
        with pytest.raises(AuthenticationError) as exc_info:
            self.auth_service.encrypt_password("")
        
        assert "密碼不能為空" in str(exc_info.value)
    
    def test_decrypt_password_success(self):
        """測試密碼解密成功"""
        password = "TestPassword456"
        encrypted = self.encryption.encrypt(password)
        
        decrypted = self.auth_service.decrypt_password(encrypted)
        assert decrypted == password
    
    def test_decrypt_password_empty(self):
        """測試空加密密碼解密失敗"""
        with pytest.raises(AuthenticationError) as exc_info:
            self.auth_service.decrypt_password("")
        
        assert "加密密碼不能為空" in str(exc_info.value)
    
    def test_decrypt_password_invalid(self):
        """測試無效加密密碼解密失敗"""
        with pytest.raises(AuthenticationError) as exc_info:
            self.auth_service.decrypt_password("invalid-encrypted-data")
        
        assert "密碼解密失敗" in str(exc_info.value)
    
    def test_validate_username_valid(self):
        """測試有效使用者名稱"""
        valid_usernames = [
            "admin",
            "user123",
            "_service",
            "test-user",
            "a",
            "very_long_username_but_valid"
        ]
        
        for username in valid_usernames:
            assert self.auth_service.validate_username(username) is True
    
    def test_validate_username_invalid(self):
        """測試無效使用者名稱"""
        invalid_usernames = [
            "",
            "  ",
            "123user",  # 不能以數字開頭
            "user@domain",  # 不能包含 @
            "user name",  # 不能包含空格
            "user!",  # 不能包含特殊字元
            "a" * 33,  # 太長
            "-user"  # 不能以 - 開頭
        ]
        
        for username in invalid_usernames:
            assert self.auth_service.validate_username(username) is False
    
    def test_validate_password_strength_strong(self):
        """測試強密碼驗證"""
        strong_password = "StrongP@ssw0rd123"
        result = self.auth_service.validate_password_strength(strong_password)
        
        assert result["valid"] is True
        assert result["score"] >= 4
        assert len(result["issues"]) == 0
    
    def test_validate_password_strength_weak(self):
        """測試弱密碼驗證"""
        weak_password = "123"
        result = self.auth_service.validate_password_strength(weak_password)
        
        assert result["valid"] is False
        assert result["score"] < 4
        assert len(result["issues"]) > 0
        assert len(result["suggestions"]) > 0
    
    def test_validate_password_strength_common(self):
        """測試常見密碼驗證"""
        common_password = "password"
        result = self.auth_service.validate_password_strength(common_password)
        
        assert result["valid"] is False
        assert "不要使用常見密碼" in result["issues"]
    
    def test_validate_password_strength_empty(self):
        """測試空密碼驗證"""
        result = self.auth_service.validate_password_strength("")
        
        assert result["valid"] is False
        assert "密碼不能為空" in result["issues"]
    
    def test_generate_secure_password(self):
        """測試生成安全密碼"""
        password = self.auth_service.generate_secure_password(16)
        
        assert len(password) == 16
        
        # 驗證密碼強度
        strength = self.auth_service.validate_password_strength(password)
        assert strength["valid"] is True
        assert strength["score"] >= 4
    
    def test_generate_secure_password_length_limits(self):
        """測試密碼長度限制"""
        # 太短的長度應該被調整為 8
        short_password = self.auth_service.generate_secure_password(4)
        assert len(short_password) == 8
        
        # 太長的長度應該被調整為 64
        long_password = self.auth_service.generate_secure_password(100)
        assert len(long_password) == 64
    
    @patch('paramiko.RSAKey.from_private_key')
    def test_validate_private_key_success(self, mock_rsa_key):
        """測試私鑰驗證成功"""
        # 模擬有效的 RSA 金鑰
        mock_key = Mock()
        mock_key.size = 2048
        mock_key.get_name.return_value = "ssh-rsa"
        mock_key.get_base64.return_value = "AAAAB3NzaC1yc2EAAA..."
        mock_rsa_key.return_value = mock_key
        
        private_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA7Z2...
-----END RSA PRIVATE KEY-----"""
        
        with patch.object(self.auth_service, '_get_key_fingerprint', return_value="aa:bb:cc:dd"):
            result = self.auth_service.validate_private_key(private_key)
        
        assert result["valid"] is True
        assert result["key_type"] == SSHKeyType.RSA
        assert result["key_size"] == 2048
        assert result["fingerprint"] == "aa:bb:cc:dd"
        assert result["has_passphrase"] is False
    
    def test_validate_private_key_empty(self):
        """測試空私鑰驗證失敗"""
        with pytest.raises(KeyValidationError) as exc_info:
            self.auth_service.validate_private_key("")
        
        assert "私鑰不能為空" in str(exc_info.value)
    
    def test_validate_private_key_invalid_format(self):
        """測試無效格式私鑰驗證失敗"""
        invalid_key = "this is not a valid private key"
        
        with pytest.raises(KeyValidationError) as exc_info:
            self.auth_service.validate_private_key(invalid_key)
        
        assert "私鑰格式錯誤" in str(exc_info.value)
    
    @patch('paramiko.RSAKey.from_private_key')
    def test_validate_private_key_with_passphrase(self, mock_rsa_key):
        """測試帶密碼的私鑰驗證"""
        mock_key = Mock()
        mock_key.size = 2048
        mock_key.get_name.return_value = "ssh-rsa"
        mock_key.get_base64.return_value = "AAAAB3NzaC1yc2EAAA..."
        mock_rsa_key.return_value = mock_key
        
        private_key = """-----BEGIN RSA PRIVATE KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: AES-128-CBC,12345...
-----END RSA PRIVATE KEY-----"""
        
        with patch.object(self.auth_service, '_get_key_fingerprint', return_value="aa:bb:cc:dd"):
            result = self.auth_service.validate_private_key(private_key, "passphrase")
        
        assert result["valid"] is True
        assert result["has_passphrase"] is True
    
    def test_detect_key_type(self):
        """測試偵測金鑰類型"""
        rsa_key = "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----"
        assert self.auth_service._detect_key_type(rsa_key) == SSHKeyType.RSA
        
        dsa_key = "-----BEGIN DSA PRIVATE KEY-----\ntest\n-----END DSA PRIVATE KEY-----"
        assert self.auth_service._detect_key_type(dsa_key) == SSHKeyType.DSA
        
        ecdsa_key = "-----BEGIN EC PRIVATE KEY-----\ntest\n-----END EC PRIVATE KEY-----"
        assert self.auth_service._detect_key_type(ecdsa_key) == SSHKeyType.ECDSA
        
        openssh_key = "-----BEGIN OPENSSH PRIVATE KEY-----\ntest\n-----END OPENSSH PRIVATE KEY-----"
        assert self.auth_service._detect_key_type(openssh_key) == SSHKeyType.ED25519
    
    def test_encrypt_private_key_success(self):
        """測試私鑰加密成功"""
        private_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA7Z2...
-----END RSA PRIVATE KEY-----"""
        
        passphrase = "test-passphrase"
        
        with patch.object(self.auth_service, 'validate_private_key') as mock_validate:
            mock_validate.return_value = {"valid": True, "key_type": SSHKeyType.RSA}
            
            encrypted_key, encrypted_passphrase = self.auth_service.encrypt_private_key(
                private_key, passphrase
            )
        
        assert encrypted_key != private_key
        assert encrypted_passphrase != passphrase
        assert len(encrypted_key) > 0
        assert len(encrypted_passphrase) > 0
        
        # 驗證可以解密
        decrypted_key, decrypted_passphrase = self.auth_service.decrypt_private_key(
            encrypted_key, encrypted_passphrase
        )
        assert decrypted_key == private_key
        assert decrypted_passphrase == passphrase
    
    def test_encrypt_private_key_no_passphrase(self):
        """測試無密碼私鑰加密"""
        private_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA7Z2...
-----END RSA PRIVATE KEY-----"""
        
        with patch.object(self.auth_service, 'validate_private_key') as mock_validate:
            mock_validate.return_value = {"valid": True, "key_type": SSHKeyType.RSA}
            
            encrypted_key, encrypted_passphrase = self.auth_service.encrypt_private_key(
                private_key, None
            )
        
        assert encrypted_key != private_key
        assert encrypted_passphrase is None
    
    def test_generate_ssh_key_pair(self):
        """測試生成 SSH 金鑰對"""
        key_pair = self.auth_service.generate_ssh_key_pair(
            key_type=SSHKeyType.RSA,
            key_size=2048
        )
        
        assert "private_key" in key_pair
        assert "public_key" in key_pair
        assert key_pair["key_type"] == SSHKeyType.RSA
        assert key_pair["key_size"] == 2048
        
        # 驗證私鑰格式
        assert "-----BEGIN" in key_pair["private_key"]
        assert "-----END" in key_pair["private_key"]
        
        # 驗證公鑰格式
        assert key_pair["public_key"].startswith("ssh-rsa")
    
    def test_generate_ssh_key_pair_unsupported_type(self):
        """測試生成不支援的金鑰類型"""
        with pytest.raises(KeyValidationError) as exc_info:
            self.auth_service.generate_ssh_key_pair(key_type="unsupported")
        
        assert "暫不支援生成" in str(exc_info.value)
    
    def test_create_server_credentials_password_only(self):
        """測試建立僅密碼認證的伺服器憑證"""
        username = "admin"
        password = "SecurePassword123!"
        
        credentials = self.auth_service.create_server_credentials(
            username=username,
            password=password
        )
        
        assert credentials["username"] == username
        assert credentials["password_encrypted"] is not None
        assert credentials["private_key_encrypted"] is None
        assert "password" in credentials["auth_type"]
        assert len(credentials["auth_type"]) == 1
    
    def test_create_server_credentials_key_only(self):
        """測試建立僅金鑰認證的伺服器憑證"""
        username = "admin"
        private_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA7Z2...
-----END RSA PRIVATE KEY-----"""
        
        with patch.object(self.auth_service, 'validate_private_key') as mock_validate:
            mock_validate.return_value = {
                "valid": True,
                "key_type": SSHKeyType.RSA,
                "fingerprint": "aa:bb:cc:dd",
                "public_key": "ssh-rsa AAAAB3... admin@test",
                "has_passphrase": False
            }
            
            credentials = self.auth_service.create_server_credentials(
                username=username,
                private_key=private_key
            )
        
        assert credentials["username"] == username
        assert credentials["password_encrypted"] is None
        assert credentials["private_key_encrypted"] is not None
        assert credentials["public_key"] is not None
        assert "key" in credentials["auth_type"]
        assert len(credentials["auth_type"]) == 1
    
    def test_create_server_credentials_both_methods(self):
        """測試建立雙重認證的伺服器憑證"""
        username = "admin"
        password = "SecurePassword123!"
        private_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA7Z2...
-----END RSA PRIVATE KEY-----"""
        
        with patch.object(self.auth_service, 'validate_private_key') as mock_validate:
            mock_validate.return_value = {
                "valid": True,
                "key_type": SSHKeyType.RSA,
                "fingerprint": "aa:bb:cc:dd",
                "public_key": "ssh-rsa AAAAB3... admin@test",
                "has_passphrase": False
            }
            
            credentials = self.auth_service.create_server_credentials(
                username=username,
                password=password,
                private_key=private_key
            )
        
        assert credentials["username"] == username
        assert credentials["password_encrypted"] is not None
        assert credentials["private_key_encrypted"] is not None
        assert credentials["public_key"] is not None
        assert "password" in credentials["auth_type"]
        assert "key" in credentials["auth_type"]
        assert len(credentials["auth_type"]) == 2
    
    def test_create_server_credentials_invalid_username(self):
        """測試無效使用者名稱建立憑證失敗"""
        with pytest.raises(AuthenticationError) as exc_info:
            self.auth_service.create_server_credentials(
                username="123invalid",
                password="password"
            )
        
        assert "使用者名稱格式無效" in str(exc_info.value)
    
    def test_create_server_credentials_no_auth_method(self):
        """測試無認證方式建立憑證失敗"""
        with pytest.raises(AuthenticationError) as exc_info:
            self.auth_service.create_server_credentials(
                username="admin"
            )
        
        assert "必須提供密碼或私鑰" in str(exc_info.value)
    
    def test_validate_credentials_success(self):
        """測試憑證驗證成功"""
        # 建立有效憑證
        username = "admin"
        password = "SecurePassword123!"
        
        credentials = self.auth_service.create_server_credentials(
            username=username,
            password=password
        )
        
        result = self.auth_service.validate_credentials(credentials)
        
        assert result["valid"] is True
        assert "password" in result["auth_methods"]
        assert len(result["issues"]) == 0
    
    def test_validate_credentials_missing_username(self):
        """測試缺少使用者名稱的憑證驗證失敗"""
        credentials = {
            "password_encrypted": "encrypted-password"
        }
        
        result = self.auth_service.validate_credentials(credentials)
        
        assert result["valid"] is False
        assert "缺少使用者名稱" in result["issues"]
    
    def test_validate_credentials_no_auth_method(self):
        """測試無認證方式的憑證驗證失敗"""
        credentials = {
            "username": "admin"
        }
        
        result = self.auth_service.validate_credentials(credentials)
        
        assert result["valid"] is False
        assert "沒有有效的認證方式" in result["issues"]


class TestAuthServiceHelpers:
    """測試認證服務便利函數"""
    
    def test_encrypt_server_password(self):
        """測試加密伺服器密碼便利函數"""
        from app.services.auth_service import encrypt_server_password
        
        password = "TestPassword123"
        encrypted = encrypt_server_password(password)
        
        assert encrypted != password
        assert len(encrypted) > 0
    
    def test_decrypt_server_password(self):
        """測試解密伺服器密碼便利函數"""
        from app.services.auth_service import decrypt_server_password, encrypt_server_password
        
        password = "TestPassword123"
        encrypted = encrypt_server_password(password)
        decrypted = decrypt_server_password(encrypted)
        
        assert decrypted == password
    
    @patch('app.services.auth_service.auth_service.validate_private_key')
    def test_validate_ssh_key(self, mock_validate):
        """測試驗證 SSH 金鑰便利函數"""
        from app.services.auth_service import validate_ssh_key
        
        mock_validate.return_value = {
            "valid": True,
            "key_type": SSHKeyType.RSA
        }
        
        private_key = "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----"
        result = validate_ssh_key(private_key)
        
        assert result["valid"] is True
        mock_validate.assert_called_once_with(private_key, None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])