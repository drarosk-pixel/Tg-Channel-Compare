# Telegram Channel Compare Bot

Ek multi-user bot jo do Telegram channels ki history compare karta hai aur batata hai har channel mein kya **missing** hai, us content ke link ke saath.

Har user bot ke andar hi `/login` karke apna account connect karta hai (phone + OTP, aur 2-step password agar ho). Koi session string kisi site pe nahi daalni padti. Comparison har user ke **apne account** se chalta hai, isliye bot wahi channels padh sakta hai jinka woh user member hai.

Check hone wala content: text, photo, video, document/file, audio, voice, GIF, sticker, poll, location, contact.

## Chalta kaise hai
1. User bot ko `/login` bhejta hai.
2. Bot phone number maangta hai → phir Telegram app pe aaya OTP → phir 2-step password (agar on hai).
3. Bot us account ka session **encrypt karke** store karta hai (per user ek session).
4. User `/compare A B` bhejta hai, bot uske account se dono channels scan karke report deta hai.

## Setup (operator ke liye)

1. **API ID / Hash:** https://my.telegram.org → *API development tools* → `api_id` aur `api_hash`.
2. **Bot token:** Telegram pe @BotFather → `/newbot` → token copy karo.
3. **Install aur configure:**
   ```bash
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   python gen_key.py          # ENCRYPTION_KEY generate karo
   cp .env.example .env        # .env mein API_ID, API_HASH, BOT_TOKEN, ENCRYPTION_KEY bharo
   ```
4. **Run:**
   ```bash
   python bot.py
   ```

Ab koi bhi user Telegram pe aapke bot ko khol ke `/login` kar sakta hai.

### Bot commands
```
/login            apna account connect karo
/compare A B      poori history compare karo
/compare A B 500  sirf latest 500 posts
/status           login status
/logout           apna session delete karo
/cancel           chal raha login rok do
```

### Channel kaise likhein
| Format | Example |
|---|---|
| Username | `@channel` ya `https://t.me/channel` |
| Private invite link | `https://t.me/+AbCdEf123` |
| Private post link / ID | `https://t.me/c/1234567890/5` ya `-1001234567890` |

User us channel ka member hona chahiye. Bot khud se kisi channel ko join nahi karta.

## Hosting (24/7)

Yeh env variables daalo (OTP site pe nahi daalni padti, users khud bot ke andar login karte hain):

| Variable | Zaruri? | Kahan se |
|---|---|---|
| `API_ID` | Haan | my.telegram.org |
| `API_HASH` | Haan | my.telegram.org |
| `BOT_TOKEN` | Haan | @BotFather |
| `ENCRYPTION_KEY` | Haan | `python gen_key.py` |
| `ALLOWED_USER_IDS` | Nahi | comma-separated user IDs; khaali = sabko allow |
| `DEFAULT_LIMIT` | Nahi | `0` = full history |

- Start command: `python bot.py` (`Procfile` mein `worker` ke roop mein already hai).
- Service type **worker/background** rakho, web nahi. Bot koi port nahi kholta.
- `data/` folder (sessions DB) persistent disk pe rakho, warna restart pe sab users ko dobara `/login` karna padega. Alternatively kisi managed DB pe shift kar sakte ho.

## Content match kaise hota hai
Ek post dusre channel mein "present" maani jaati hai agar inmein se koi bhi match ho:
1. **Forward:** woh post dusre channel se forward ki gayi ho.
2. **Same file:** same photo/document ID.
3. **Re-upload:** same file size + type + duration.
4. **Same text:** links, @mentions, emojis, punctuation hata ke text match. Isliye `@channelA` ko `@channelB` se replace karne par bhi match ho jaata hai.
5. **Media caption:** sirf tab jab caption 20+ characters ka ho (chhote captions se galat match nahi hota).

## Single-account mode (optional)
Agar sirf apne liye chahiye, bina bot ke, to purane scripts bhi hain:
- `python login.py` → ek baar OTP se login, session file/string banata hai.
- `python userbot.py` → aapke Saved Messages se `.compare A B` chalta hai.
- `python compare_cli.py @A @B` → terminal se direct.

## Security (zaroor padho)
- **Operator ke paas sab logged-in accounts ka access aa jaata hai.** Sessions `ENCRYPTION_KEY` se encrypt hote hain, lekin key bhi operator ke paas hai. Users ko sirf tabhi login karna chahiye jab woh aap (operator) par bharosa karein. Bot `/login` par yeh warning dikhata hai.
- `ENCRYPTION_KEY`, `BOT_TOKEN`, `API_HASH` sirf env variables mein rakho — code ya GitHub mein kabhi nahi. `.env` aur `data/` already `.gitignore` mein hain.
- OTP chat mein plain na aaye isliye bot users ko digits ke beech space daalne ko kehta hai (`1 2 3 4 5`); bot phir sirf digits nikaalta hai.
- Bot kuch delete/forward/post nahi karta, sirf channels **padhta** hai aur report bhejta hai.
- Ek hi server IP se bahut saare accounts login karne par Telegram restriction laga sakta hai. Zyada users ho to dhyan rakho.
- User `/logout` se apna session hata sakta hai. Account se poori tarah hatana ho to Telegram → Settings → Devices mein woh session terminate karein.
