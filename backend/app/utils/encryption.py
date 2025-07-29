"""
CWatcher 加密工具模組

提供 AES-256-GCM 加密功能，用於安全存儲 SSH 憑證
支援對稱加密/解密操作，確保敏感資訊的安全性
"""

import os
import base64
from typing import Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import secrets


class EncryptionError(Exception):
    """加密相關錯誤"""
    pass


class AESGCMEncryption:
    """
    AES-256-GCM 加密工具類別
    
    提供高安全性的對稱加密功能，適用於 SSH 憑證的安全存儲
    使用 Galois/Counter Mode (GCM) 模式，提供加密和認證
    """
    
    def __init__(self, master_key: Optional[str] = None):
        """
        初始化加密器
        
        Args:
            master_key: 主密鑰，如果未提供則從環境變數讀取
        """
        self.master_key = master_key or os.getenv(
            'CWATCHER_MASTER_KEY', 
            'default-master-key-change-in-production'
        )
        
        if len(self.master_key.encode()) < 32:
            # 使用 PBKDF2 擴展短密鑰
            self._derived_key = self._derive_key(self.master_key)
        else:
            self._derived_key = self.master_key.encode()[:32]
    
    def _derive_key(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """
        使用 PBKDF2 從密碼派生密鑰
        
        Args:
            password: 原始密碼
            salt: 鹽值，如果未提供則生成新的
            
        Returns:
            派生的 32 位元組密鑰
        """
        if salt is None:
            salt = b'cwatcher-salt-2024'  # 固定鹽值以確保一致性
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(password.encode())
    
    def encrypt(self, plaintext: str) -> str:
        """
        加密字串
        
        Args:
            plaintext: 要加密的明文字串
            
        Returns:
            Base64 編碼的加密資料，格式：nonce:ciphertext
            
        Raises:
            EncryptionError: 加密失敗時拋出
        """
        try:
            if not plaintext:
                raise EncryptionError("明文不能為空")
            
            # 使用 AES-GCM 加密
            aesgcm = AESGCM(self._derived_key)
            nonce = secrets.token_bytes(12)  # GCM 建議 12 位元組 nonce
            
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
            
            # 組合 nonce 和密文，然後 Base64 編碼
            encrypted_data = nonce + ciphertext
            return base64.b64encode(encrypted_data).decode()
            
        except Exception as e:
            raise EncryptionError(f"加密失敗: {str(e)}")
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        解密字串
        
        Args:
            encrypted_data: Base64 編碼的加密資料
            
        Returns:
            解密後的明文字串
            
        Raises:
            EncryptionError: 解密失敗時拋出
        """
        try:
            if not encrypted_data:
                raise EncryptionError("加密資料不能為空")
            
            # Base64 解碼
            raw_data = base64.b64decode(encrypted_data.encode())
            
            if len(raw_data) < 12:
                raise EncryptionError("加密資料格式錯誤")
            
            # 分離 nonce 和密文
            nonce = raw_data[:12]
            ciphertext = raw_data[12:]
            
            # 使用 AES-GCM 解密
            aesgcm = AESGCM(self._derived_key)
            decrypted_data = aesgcm.decrypt(nonce, ciphertext, None)
            
            return decrypted_data.decode()
            
        except Exception as e:
            raise EncryptionError(f"解密失敗: {str(e)}")
    
    def encrypt_credentials(self, username: str, password: str) -> Tuple[str, str]:
        """
        加密 SSH 憑證
        
        Args:
            username: 使用者名稱
            password: 密碼
            
        Returns:
            (加密的使用者名稱, 加密的密碼)
        """
        return self.encrypt(username), self.encrypt(password)
    
    def decrypt_credentials(self, encrypted_username: str, encrypted_password: str) -> Tuple[str, str]:
        """
        解密 SSH 憑證
        
        Args:
            encrypted_username: 加密的使用者名稱
            encrypted_password: 加密的密碼
            
        Returns:
            (使用者名稱, 密碼)
        """
        return self.decrypt(encrypted_username), self.decrypt(encrypted_password)


# 全域加密器實例
encryption = AESGCMEncryption()


def encrypt_text(plaintext: str) -> str:
    """便利函數：加密文本"""
    return encryption.encrypt(plaintext)


def decrypt_text(ciphertext: str) -> str:
    """便利函數：解密文本"""
    return encryption.decrypt(ciphertext)


def verify_encryption() -> bool:
    """
    驗證加密功能是否正常工作
    
    Returns:
        True 如果加密/解密正常工作
    """
    try:
        test_data = "test-encryption-data-2024"
        encrypted = encrypt_text(test_data)
        decrypted = decrypt_text(encrypted)
        return decrypted == test_data
    except Exception:
        return False


if __name__ == "__main__":
    # 測試加密功能
    print("🔐 測試 AES-GCM 加密功能...")
    
    if verify_encryption():
        print("✅ 加密功能測試通過")
        
        # 示例使用
        sample_password = "my-secure-password-123"
        encrypted = encrypt_text(sample_password)
        decrypted = decrypt_text(encrypted)
        
        print(f"原文: {sample_password}")
        print(f"加密: {encrypted}")
        print(f"解密: {decrypted}")
        print(f"驗證: {'通過' if sample_password == decrypted else '失敗'}")
    else:
        print("❌ 加密功能測試失敗")