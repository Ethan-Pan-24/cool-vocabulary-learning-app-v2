# Production Deployment Configuration

## Production URL
https://lab-i7-ethan-test.hat-and-cat.cc/

## ⚙️ Server Configuration

The application is configured to run behind a reverse proxy (nginx/caddy) that handles:
- HTTPS/SSL certificates
- Domain routing
- Port forwarding to the FastAPI app

### What Changed
- **Host binding:** Changed from `127.0.0.1` (localhost only) to `0.0.0.0` (all interfaces)
- **Port:** Still runs on port 8000 internally
- **Reverse proxy:** Handles HTTPS and forwards requests to port 8000

---

## 🔐 Google OAuth Configuration

> [!IMPORTANT]
> You must update your Google OAuth settings to include the production domain.

### Steps:
1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Select your OAuth 2.0 Client ID
3. Add to **Authorized redirect URIs**:
   ```
   https://lab-i7-ethan-test.hat-and-cat.cc/auth/google
   ```
4. Save changes

### Environment Variables
Make sure your `.env` file has the correct credentials:
```env
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
```

---

## 🚀 Deployment Checklist

- [ ] Update `.env` with production values
- [ ] Configure reverse proxy (nginx/caddy) for HTTPS
- [ ] Update Google OAuth redirect URIs
- [ ] Set `SESSION_SECRET_KEY` to a strong random value
- [ ] Disable `reload=True` in production (optional)
- [ ] Run server: `python main.py`

---

## 📝 Example Nginx Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name lab-i7-ethan-test.hat-and-cat.cc;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 🔄 OAuth Flow

1. User clicks "Login with Google"
2. Redirects to Google OAuth: `/login/google`
3. User authorizes
4. Google redirects back to: `https://lab-i7-ethan-test.hat-and-cat.cc/auth/google`
5. Server processes token and logs user in

The OAuth redirect URI uses `request.url_for('auth_google')` which automatically generates the correct URL based on the incoming request, so it should work with your production domain.

---

## ✅ Testing

After deployment:
1. Visit: https://lab-i7-ethan-test.hat-and-cat.cc/
2. Test Google OAuth login
3. Check admin access at: https://lab-i7-ethan-test.hat-and-cat.cc/97110424
