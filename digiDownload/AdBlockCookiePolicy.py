from http.cookiejar import DefaultCookiePolicy, Cookie


class AdBlockPolicy(DefaultCookiePolicy):
    def set_ok(self, cookie: Cookie, _) -> bool:
        return cookie.name != "ad_session_id"
