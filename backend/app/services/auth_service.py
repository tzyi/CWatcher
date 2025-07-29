"""
CWatcher 認證服務

提供 SSH 憑證的安全管理功能
支援密碼認證、SSH 金鑰認證和憑證加密存儲
"""

import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path
import paramiko
from paramiko import RSAKey, DSSKey, ECDSAKey, Ed25519Key
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import secrets
import string

from utils.encryption import AESGCMEncryption, EncryptionError
from core.config import settings


logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """認證相關錯誤"""
    pass


class KeyValidationError(Exception):
    """金鑰驗證錯誤"""
    pass


class SSHKeyType:
    """SSH 金鑰類型常數"""
    RSA = "rsa"
    DSA = "dsa"
    ECDSA = "ecdsa"
    ED25519 = "ed25519"


class AuthService:
    """
    SSH 認證服務
    
    提供憑證加密、解密、驗證和管理功能
    支援多種 SSH 金鑰格式和安全存儲
    """
    
    def __init__(self, encryption: Optional[AESGCMEncryption] = None):
        self.encryption = encryption or AESGCMEncryption()
        
        # 支援的金鑰類型映射
        self.key_types = {
            SSHKeyType.RSA: RSAKey,
            SSHKeyType.DSA: DSSKey,
            SSHKeyType.ECDSA: ECDSAKey,
            SSHKeyType.ED25519: Ed25519Key
        }
    
    def encrypt_password(self, password: str) -> str:
        """
        加密密碼
        
        Args:
            password: 明文密碼
            
        Returns:
            加密後的密碼
        """
        if not password:
            raise AuthenticationError("密碼不能為空")
        
        try:
            return self.encryption.encrypt(password)
        except EncryptionError as e:
            raise AuthenticationError(f"密碼加密失敗: {e}")
    
    def decrypt_password(self, encrypted_password: str) -> str:
        """
        解密密碼
        
        Args:
            encrypted_password: 加密的密碼
            
        Returns:
            明文密碼
        """
        if not encrypted_password:
            raise AuthenticationError("加密密碼不能為空")
        
        try:
            return self.encryption.decrypt(encrypted_password)
        except EncryptionError as e:
            raise AuthenticationError(f"密碼解密失敗: {e}")
    
    def encrypt_private_key(self, private_key: str, passphrase: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """
        加密私鑰
        
        Args:
            private_key: PEM 格式的私鑰
            passphrase: 金鑰密碼（如果有）
            
        Returns:
            (加密的私鑰, 加密的密碼)
        """
        if not private_key:
            raise AuthenticationError("私鑰不能為空")
        
        try:
            # 驗證私鑰格式
            self.validate_private_key(private_key, passphrase)
            
            encrypted_key = self.encryption.encrypt(private_key)
            encrypted_passphrase = None
            
            if passphrase:
                encrypted_passphrase = self.encryption.encrypt(passphrase)
            
            return encrypted_key, encrypted_passphrase
            
        except (KeyValidationError, EncryptionError) as e:
            raise AuthenticationError(f"私鑰加密失敗: {e}")
    
    def decrypt_private_key(self, encrypted_key: str, encrypted_passphrase: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """
        解密私鑰
        
        Args:
            encrypted_key: 加密的私鑰
            encrypted_passphrase: 加密的密碼
            
        Returns:
            (私鑰, 密碼)
        """
        if not encrypted_key:
            raise AuthenticationError("加密私鑰不能為空")
        
        try:
            private_key = self.encryption.decrypt(encrypted_key)
            passphrase = None
            
            if encrypted_passphrase:
                passphrase = self.encryption.decrypt(encrypted_passphrase)
            
            return private_key, passphrase
            
        except EncryptionError as e:
            raise AuthenticationError(f"私鑰解密失敗: {e}")
    
    def validate_private_key(self, private_key: str, passphrase: Optional[str] = None) -> Dict[str, Any]:
        """
        驗證私鑰格式和有效性
        
        Args:
            private_key: PEM 格式的私鑰
            passphrase: 金鑰密碼
            
        Returns:
            金鑰資訊字典
            
        Raises:
            KeyValidationError: 金鑰無效
        """
        if not private_key or not private_key.strip():
            raise KeyValidationError("私鑰不能為空")
        
        # 檢查基本格式
        if not ("-----BEGIN" in private_key and "-----END" in private_key):
            raise KeyValidationError("私鑰格式錯誤，必須是 PEM 格式")
        
        # 檢測金鑰類型
        key_type = self._detect_key_type(private_key)
        
        try:
            # 嘗試載入金鑰
            from io import StringIO
            key_obj = None
            
            if key_type == SSHKeyType.RSA:
                key_obj = RSAKey.from_private_key(StringIO(private_key), password=passphrase)
            elif key_type == SSHKeyType.DSA:
                key_obj = DSSKey.from_private_key(StringIO(private_key), password=passphrase)
            elif key_type == SSHKeyType.ECDSA:
                key_obj = ECDSAKey.from_private_key(StringIO(private_key), password=passphrase)
            elif key_type == SSHKeyType.ED25519:
                key_obj = Ed25519Key.from_private_key(StringIO(private_key), password=passphrase)
            else:
                raise KeyValidationError(f"不支援的金鑰類型: {key_type}")
            
            # 取得公鑰
            public_key = self._get_public_key_from_private(key_obj)
            
            return {
                "valid": True,
                "key_type": key_type,
                "key_size": getattr(key_obj, 'size', None),
                "fingerprint": self._get_key_fingerprint(key_obj),
                "public_key": public_key,
                "has_passphrase": passphrase is not None
            }
            
        except paramiko.PasswordRequiredException:
            raise KeyValidationError("私鑰需要密碼")
        except paramiko.SSHException as e:
            raise KeyValidationError(f"私鑰格式錯誤: {e}")
        except Exception as e:
            raise KeyValidationError(f"金鑰驗證失敗: {e}")
    
    def _detect_key_type(self, private_key: str) -> str:
        """偵測私鑰類型"""
        private_key_upper = private_key.upper()
        
        if "RSA PRIVATE KEY" in private_key_upper or "BEGIN PRIVATE KEY" in private_key_upper:
            return SSHKeyType.RSA
        elif "DSA PRIVATE KEY" in private_key_upper:
            return SSHKeyType.DSA
        elif "EC PRIVATE KEY" in private_key_upper:
            return SSHKeyType.ECDSA
        elif "OPENSSH PRIVATE KEY" in private_key_upper:
            # OpenSSH 格式可能是 Ed25519 或其他類型
            return SSHKeyType.ED25519
        else:
            return SSHKeyType.RSA  # 默認為 RSA
    
    def _get_public_key_from_private(self, key_obj) -> str:
        """從私鑰物件取得公鑰字串"""
        try:
            return f"{key_obj.get_name()} {key_obj.get_base64()}"
        except Exception as e:
            logger.warning(f"無法取得公鑰: {e}")
            return ""
    
    def _get_key_fingerprint(self, key_obj) -> str:
        """取得金鑰指紋"""
        try:
            import hashlib
            key_data = key_obj.asbytes()
            fingerprint = hashlib.md5(key_data).hexdigest()
            # 格式化為 xx:xx:xx 格式
            return ':'.join(fingerprint[i:i+2] for i in range(0, len(fingerprint), 2))
        except Exception as e:
            logger.warning(f"無法計算金鑰指紋: {e}")
            return ""
    
    def validate_username(self, username: str) -> bool:
        """
        驗證使用者名稱格式
        
        Args:
            username: 使用者名稱
            
        Returns:
            是否有效
        """
        if not username or not username.strip():
            return False
        
        # Linux 使用者名稱規則
        pattern = r'^[a-zA-Z_][a-zA-Z0-9_-]*$'
        
        if not re.match(pattern, username):
            return False
        
        # 長度限制
        if len(username) > 32:
            return False
        
        return True
    
    def validate_password_strength(self, password: str) -> Dict[str, Any]:
        """
        驗證密碼強度
        
        Args:
            password: 密碼
            
        Returns:
            驗證結果字典
        """
        result = {
            "valid": False,
            "score": 0,
            "issues": [],
            "suggestions": []
        }
        
        if not password:
            result["issues"].append("密碼不能為空")
            return result
        
        score = 0
        
        # 長度檢查
        if len(password) >= 8:
            score += 2
        elif len(password) >= 6:
            score += 1
        else:
            result["issues"].append("密碼長度至少 6 位元")
        
        # 複雜度檢查
        if re.search(r'[a-z]', password):
            score += 1
        else:
            result["suggestions"].append("包含小寫字母")
        
        if re.search(r'[A-Z]', password):
            score += 1
        else:
            result["suggestions"].append("包含大寫字母")
        
        if re.search(r'\d', password):
            score += 1
        else:
            result["suggestions"].append("包含數字")
        
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 1
        else:
            result["suggestions"].append("包含特殊字元")
        
        # 常見密碼檢查
        common_passwords = ["password", "123456", "admin", "root", "user"]
        if password.lower() in common_passwords:
            result["issues"].append("不要使用常見密碼")
            score -= 2
        
        result["score"] = max(0, score)
        result["valid"] = score >= 4 and len(result["issues"]) == 0
        
        return result
    
    def generate_ssh_key_pair(self, key_type: str = SSHKeyType.RSA, key_size: int = 2048) -> Dict[str, str]:
        """
        生成 SSH 金鑰對
        
        Args:
            key_type: 金鑰類型
            key_size: 金鑰大小
            
        Returns:
            包含私鑰和公鑰的字典
        """
        try:
            if key_type == SSHKeyType.RSA:
                # 生成 RSA 金鑰對
                key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=key_size
                )
                
                # 序列化私鑰
                private_pem = key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.OpenSSH,
                    encryption_algorithm=serialization.NoEncryption()
                ).decode('utf-8')
                
                # 序列化公鑰
                public_key = key.public_key()
                public_pem = public_key.public_bytes(
                    encoding=serialization.Encoding.OpenSSH,
                    format=serialization.PublicFormat.OpenSSH
                ).decode('utf-8')
                
                return {
                    "private_key": private_pem,
                    "public_key": public_pem,
                    "key_type": key_type,
                    "key_size": key_size
                }
            else:
                raise KeyValidationError(f"暫不支援生成 {key_type} 類型的金鑰")
                
        except Exception as e:
            raise KeyValidationError(f"金鑰生成失敗: {e}")
    
    def create_server_credentials(
        self, 
        username: str, 
        password: Optional[str] = None, 
        private_key: Optional[str] = None,
        key_passphrase: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        建立並加密伺服器認證資訊
        
        Args:
            username: 使用者名稱
            password: 密碼
            private_key: 私鑰
            key_passphrase: 金鑰密碼
            
        Returns:
            加密後的認證資訊
        """
        if not self.validate_username(username):
            raise AuthenticationError("使用者名稱格式無效")
        
        if not password and not private_key:
            raise AuthenticationError("必須提供密碼或私鑰")
        
        credentials = {
            "username": username,
            "password_encrypted": None,
            "private_key_encrypted": None,
            "key_passphrase_encrypted": None,
            "public_key": None,
            "auth_type": [],
            "created_at": datetime.now().isoformat()
        }
        
        # 處理密碼認證
        if password:
            # 驗證密碼強度
            password_check = self.validate_password_strength(password)
            if not password_check["valid"]:
                logger.warning(f"密碼強度不足: {password_check['issues']}")
            
            credentials["password_encrypted"] = self.encrypt_password(password)
            credentials["auth_type"].append("password")
        
        # 處理金鑰認證
        if private_key:
            key_info = self.validate_private_key(private_key, key_passphrase)
            
            encrypted_key, encrypted_passphrase = self.encrypt_private_key(
                private_key, key_passphrase
            )
            
            credentials["private_key_encrypted"] = encrypted_key
            credentials["key_passphrase_encrypted"] = encrypted_passphrase
            credentials["public_key"] = key_info["public_key"]
            credentials["auth_type"].append("key")
            credentials["key_info"] = {
                "key_type": key_info["key_type"],
                "fingerprint": key_info["fingerprint"],
                "has_passphrase": key_info["has_passphrase"]
            }
        
        return credentials
    
    def validate_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        驗證認證資訊的完整性
        
        Args:
            credentials: 認證資訊字典
            
        Returns:
            驗證結果
        """
        result = {
            "valid": False,
            "auth_methods": [],
            "issues": []
        }
        
        try:
            # 檢查使用者名稱
            if not credentials.get("username"):
                result["issues"].append("缺少使用者名稱")
                return result
            
            # 檢查密碼認證
            if credentials.get("password_encrypted"):
                try:
                    password = self.decrypt_password(credentials["password_encrypted"])
                    if password:
                        result["auth_methods"].append("password")
                except Exception as e:
                    result["issues"].append(f"密碼解密失敗: {e}")
            
            # 檢查金鑰認證
            if credentials.get("private_key_encrypted"):
                try:
                    private_key, passphrase = self.decrypt_private_key(
                        credentials["private_key_encrypted"],
                        credentials.get("key_passphrase_encrypted")
                    )
                    
                    if private_key:
                        # 驗證金鑰
                        self.validate_private_key(private_key, passphrase)
                        result["auth_methods"].append("key")
                        
                except Exception as e:
                    result["issues"].append(f"私鑰驗證失敗: {e}")
            
            # 至少要有一種認證方式
            if not result["auth_methods"]:
                result["issues"].append("沒有有效的認證方式")
            else:
                result["valid"] = True
            
            return result
            
        except Exception as e:
            result["issues"].append(f"驗證過程出錯: {e}")
            return result
    
    def generate_secure_password(self, length: int = 16) -> str:
        """
        生成安全密碼
        
        Args:
            length: 密碼長度
            
        Returns:
            隨機密碼
        """
        if length < 8:
            length = 8
        elif length > 64:
            length = 64
        
        # 定義字元集合
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        symbols = "!@#$%^&*"
        
        # 確保至少包含每種字元
        password = [
            secrets.choice(lowercase),
            secrets.choice(uppercase),
            secrets.choice(digits),
            secrets.choice(symbols)
        ]
        
        # 填充剩餘長度
        all_chars = lowercase + uppercase + digits + symbols
        for _ in range(length - 4):
            password.append(secrets.choice(all_chars))
        
        # 隨機打亂
        secrets.SystemRandom().shuffle(password)
        
        return ''.join(password)


# 全域認證服務實例
auth_service = AuthService()


# 便利函數
def encrypt_server_password(password: str) -> str:
    """加密伺服器密碼的便利函數"""
    return auth_service.encrypt_password(password)


def decrypt_server_password(encrypted_password: str) -> str:
    """解密伺服器密碼的便利函數"""
    return auth_service.decrypt_password(encrypted_password)


def validate_ssh_key(private_key: str, passphrase: Optional[str] = None) -> Dict[str, Any]:
    """驗證 SSH 金鑰的便利函數"""
    return auth_service.validate_private_key(private_key, passphrase)


if __name__ == "__main__":
    # 測試認證服務
    print("🔐 測試認證服務...")
    
    try:
        # 測試密碼加密
        test_password = "SecurePassword123!"
        encrypted = auth_service.encrypt_password(test_password)
        decrypted = auth_service.decrypt_password(encrypted)
        print(f"密碼加密測試: {'通過' if test_password == decrypted else '失敗'}")
        
        # 測試密碼強度驗證
        strength = auth_service.validate_password_strength(test_password)
        print(f"密碼強度: {strength}")
        
        # 測試生成密碼
        generated = auth_service.generate_secure_password(16)
        print(f"生成的密碼: {generated}")
        
        # 測試金鑰生成
        key_pair = auth_service.generate_ssh_key_pair()
        print(f"生成金鑰對: {key_pair['key_type']}, 大小: {key_pair['key_size']}")
        
        # 測試金鑰驗證
        key_info = auth_service.validate_private_key(key_pair["private_key"])
        print(f"金鑰驗證: {key_info}")
        
        print("✅ 認證服務測試完成")
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")