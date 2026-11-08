# Telegram Channel Compare Userbot

Yeh tool aapke **apne Telegram account** se login karta hai (phone + OTP), koi bot channel mein add nahi karna padta. Do channels ki poori history padhta hai aur batata hai:

- **Channel B mein kya missing hai** jo Channel A mein hai, us post ke link ke saath (A mein)
- **Channel A mein kya missing hai** jo B mein hai, link ke saath (B mein)

Har type ka content check hota hai: text, photo, video, document/file, audio, voice, GIF, sticker, poll, location, contact.

## Setup

1. **API ID / Hash lo:** https://my.telegram.org → login → *API development tools* → app banao → `api_id` aur `api_hash` copy karo.
2. **Install:**
   ```bash
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env      # phir .env mein API_ID, API_HASH, PHONE bharo
   ```
3. **Login (sirf ek baar):**
   ```bash
   python login.py
   ```
   Telegram app pe OTP aayega, woh daalo. 2-Step Verification on hai to password bhi maangega. Session `sessions/userbot.session` mein save ho jaata hai.

## Use karne ke 2 tareeke

### 1. Telegram se (userbot mode)
```bash
python userbot.py
```
Ab apne Telegram ke **Saved Messages** mein type karo:
```
.compare @otherchannel https://t.me/+MyPrivateInvite
.compare @otherchannel @mychannel 500     # sirf latest 500 posts
.help
```
Summary aur links wahi reply mein aayenge, aur poori list HTML + CSV file ke roop mein bhejega. Commands sirf aapke Saved Messages se chalte hain, koi aur trigger nahi kar sakta.

### 2. Terminal se
```bash
python compare_cli.py @otherchannel -1001234567890
python compare_cli.py @otherchannel @mychannel --limit 500
```
Report `reports/` folder mein banti hai.

### Channel kaise likhein
| Format | Example |
|---|---|
| Username | `@channel` ya `https://t.me/channel` |
| Private invite link | `https://t.me/+AbCdEf123` |
| Private post link / ID | `https://t.me/c/1234567890/5` ya `-1001234567890` |

Account us channel ka member hona chahiye (private ke liye). Tool khud se kisi channel ko join nahi karta.

## Hosting (24/7 chalane ke liye)

OTP server pe nahi daal sakte, isliye pehle **apne computer pe** `python login.py` chalao aur `y` daal ke `SESSION_STRING` copy karo.

Hosting (Railway, Render, Koyeb, Heroku, VPS) pe yeh environment variables daalo:

| Variable | Zaruri? | Kahan se milega |
|---|---|---|
| `API_ID` | Haan | https://my.telegram.org → API development tools |
| `API_HASH` | Haan | Wahi se |
| `SESSION_STRING` | Haan | `python login.py` ka output |
| `DEFAULT_LIMIT` | Nahi | `0` = full history |

- Start command: `python userbot.py` (`Procfile` mein `worker` ke roop mein already hai)
- Service type **worker / background** rakho, web nahi. Yeh koi port nahi kholta.
- `PHONE` hosting pe nahi chahiye.

## Content match kaise hota hai

Ek post dusre channel mein "present" maani jaati hai agar inmein se koi bhi match ho:

1. **Forward:** B mein woh post A se forward ki gayi hai
2. **Same file:** same photo/document ID (file dobara bheji gayi)
3. **Re-upload:** same file size + file type + duration (video/audio/document)
4. **Same text:** text match, links, @mentions, emojis aur punctuation hata ke. Isliye `@channelA` ko `@channelB` se replace karne par bhi match ho jaata hai.
5. **Media caption:** sirf tab, jab caption 20+ characters ka ho. "Episode 1" jaise chhote captions se galat match nahi hota.

## Limitations
- **Re-upload ki hui photo bina caption ke:** Telegram photo ko compress karta hai, isliye photo ID alag ho jaati hai. Aisi photo galti se "missing" dikh sakti hai.
- **Edit/compress karke dobara upload ki gayi video** ka size alag hota hai, to woh bhi missing dikhegi agar caption 20 characters se chhota ho.
- `limit` lagane par sirf latest N posts compare hoti hain. Purana content jo limit ke bahar hai, missing dikh sakta hai. Exact result ke liye limit 0 (full history) rakho.
- Bade channels (50k+ posts) mein kuch minute lagte hain. Telegram rate limit (FloodWait) aaye to tool apne aap wait karta hai.

## Security
- `SESSION_STRING` aur `sessions/*.session` file se aapke account ka **poora access** milta hai. Leak ho jaye to Telegram → Settings → Devices mein woh session terminate karo.
- `sessions/*.session` file se aapke account ka **poora access** milta hai. Ise kisi ko na do, GitHub par upload na karo (`.gitignore` mein already hai).
- Tool sirf messages **padhta** hai. Woh kuch delete, forward ya post nahi karta, sirf aapke Saved Messages mein report bhejta hai.
- Userbot Telegram ke rules ke grey area mein aata hai. Sirf padhna low-risk hai, phir bhi zarurat ho to alag account use karo.
