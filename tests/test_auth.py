"""
認証機能のテスト
spec.md セクション4 認証API参照
"""
import pytest
from tests.conftest import create_test_store


class TestLogin:
    def test_login_page_renders(self, client):
        """ログインページが正常に表示される"""
        resp = client.get("/store/login")
        assert resp.status_code == 200
        assert "ログイン" in resp.text

    def test_login_success(self, client, test_store):
        """正しい認証情報でログイン成功 → ダッシュボードへリダイレクト"""
        resp = client.post(
            "/store/login",
            data={"phone_number": "090-1234-5678", "password": "testpass123"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/store/dashboard" in resp.headers["location"]

    def test_login_wrong_password(self, client, test_store):
        """誤パスワードでログイン失敗"""
        resp = client.post(
            "/store/login",
            data={"phone_number": "090-1234-5678", "password": "wrongpass"},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        assert "電話番号またはパスワードが違います" in resp.text

    def test_login_wrong_phone(self, client):
        """存在しない電話番号でログイン失敗"""
        resp = client.post(
            "/store/login",
            data={"phone_number": "999-9999-9999", "password": "pass"},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        assert "電話番号またはパスワードが違います" in resp.text

    def test_dashboard_requires_auth(self, client):
        """未ログインでダッシュボードアクセス → ログインへリダイレクト"""
        resp = client.get("/store/dashboard", follow_redirects=False)
        assert resp.status_code in (302, 422)

    def test_logout(self, logged_in_client):
        """ログアウト後はセッションが破棄される"""
        resp = logged_in_client.get("/store/logout", follow_redirects=False)
        assert resp.status_code == 302
        assert "/store/login" in resp.headers["location"]

    def test_already_logged_in_redirects(self, logged_in_client):
        """ログイン済みでログインページ → ダッシュボードへリダイレクト"""
        resp = logged_in_client.get("/store/login", follow_redirects=False)
        assert resp.status_code == 302
        assert "/store/dashboard" in resp.headers["location"]
