import os
import sqlite3
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'orbit.db')
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

WAYPOINT_BLUE = 0x005B96

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} for Orbit CRM')

@bot.group(invoke_without_command=True)
async def orbit(ctx):
    embed = discord.Embed(title="Orbit Commands", color=WAYPOINT_BLUE)
    embed.add_field(name="!orbit summary", value="Territory health snapshot", inline=False)
    embed.add_field(name="!orbit account [name]", value="Account brief for named account", inline=False)
    embed.add_field(name="!orbit quotes", value="Lists all open quotes", inline=False)
    embed.add_field(name="!orbit atrisk", value="Lists accounts with health score < 60", inline=False)
    embed.add_field(name="!orbit wizard [query]", value="Passes query to Wizard AI", inline=False)
    embed.add_field(name="!orbit edd [account]", value="Returns EDD status for account", inline=False)
    await ctx.send(embed=embed)

@orbit.command(name="summary")
async def summary(ctx):
    conn = get_db()
    total = conn.execute("SELECT count(*) as c FROM accounts").fetchone()['c']
    at_risk = conn.execute("SELECT count(*) as c FROM accounts WHERE health_score < 60").fetchone()['c']
    rev = conn.execute("SELECT sum(ytd_revenue) as r FROM accounts").fetchone()['r'] or 0
    quotes = conn.execute("SELECT count(*) as c FROM quotes WHERE status NOT IN ('Accepted', 'Declined')").fetchone()['c']
    
    embed = discord.Embed(title="Territory Health Snapshot", color=WAYPOINT_BLUE)
    embed.add_field(name="Total Accounts", value=str(total), inline=True)
    embed.add_field(name="At-Risk", value=f"{at_risk} ⚠️", inline=True)
    embed.add_field(name="Open Quotes", value=str(quotes), inline=True)
    embed.add_field(name="YTD Revenue", value=f"${rev:,.2f}", inline=False)
    embed.set_footer(text="Orbit | Waypoint Analytical")
    await ctx.send(embed=embed)

@orbit.command(name="account")
async def account(ctx, *, name: str):
    conn = get_db()
    acc = conn.execute("SELECT * FROM accounts WHERE name LIKE ?", (f"%{name}%",)).fetchone()
    if not acc:
        await ctx.send(f"Account '{name}' not found.")
        return
        
    quotes = conn.execute("SELECT sum(amount) as total, count(*) as count FROM quotes WHERE account_id=? AND status NOT IN ('Accepted', 'Declined')", (acc['id'],)).fetchone()
    quote_str = f"{quotes['count']} (${quotes['total'] or 0:,.2f} total)"
    
    health = acc['health_score']
    health_icon = "🟢" if health >= 80 else "🟡" if health >= 60 else "🔴"
    
    # Days since contact calculation omitted for brevity, assuming standard formatting
    embed = discord.Embed(title=f"{acc['name']} — Account Brief", color=WAYPOINT_BLUE)
    embed.add_field(name="Health Score", value=f"{health}/100 {health_icon}", inline=True)
    embed.add_field(name="Last Contact", value=acc['last_contact_date'] or "Unknown", inline=True)
    embed.add_field(name="Open Quotes", value=quote_str, inline=True)
    embed.add_field(name="Pipeline Stage", value=acc['pipeline_stage'] or "Unknown", inline=False)
    embed.add_field(name="YTD Revenue", value=f"${acc['ytd_revenue'] or 0:,.2f}", inline=True)
    embed.set_footer(text="Orbit | Waypoint Analytical")
    await ctx.send(embed=embed)

@orbit.command(name="quotes")
async def open_quotes(ctx):
    conn = get_db()
    quotes = conn.execute("""
        SELECT q.quote_number, q.amount, q.sent_date, a.name 
        FROM quotes q JOIN accounts a ON q.account_id = a.id 
        WHERE q.status NOT IN ('Accepted', 'Declined')
        ORDER BY q.sent_date DESC LIMIT 10
    """).fetchall()
    
    embed = discord.Embed(title="Open Quotes", color=WAYPOINT_BLUE)
    for q in quotes:
        embed.add_field(name=f"{q['name']} ({q['quote_number']})", value=f"${q['amount']:,.2f} - Sent: {q['sent_date']}", inline=False)
    if not quotes:
        embed.description = "No open quotes."
    embed.set_footer(text="Orbit | Waypoint Analytical")
    await ctx.send(embed=embed)

@orbit.command(name="atrisk")
async def atrisk(ctx):
    conn = get_db()
    accs = conn.execute("SELECT name, health_score, last_contact_date FROM accounts WHERE health_score < 60 ORDER BY health_score ASC").fetchall()
    
    embed = discord.Embed(title="At-Risk Accounts", color=0xEB5757)
    for a in accs:
        embed.add_field(name=a['name'], value=f"Health: {a['health_score']} | Last Contact: {a['last_contact_date'] or 'Never'}", inline=False)
    if not accs:
        embed.description = "No at-risk accounts found."
    embed.set_footer(text="Orbit | Waypoint Analytical")
    await ctx.send(embed=embed)

@orbit.command(name="wizard")
async def wizard(ctx, *, query: str):
    import requests
    response_msg = "Please wait, consulting Orbit Wizard..."
    msg = await ctx.send(response_msg)
    
    try:
        # Just use requests to hit the local running API endpoint. 
        # But this is SSE streaming. We can just take the concatenated text.
        res = requests.post('http://127.0.0.1:5000/api/wizard/query', json={"query": query}, stream=True)
        full_text = ""
        for line in res.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith("data: "):
                    import json
                    try:
                        data = json.loads(decoded[6:])
                        if data.get('done'):
                            break
                        if data.get('text'):
                            full_text += data['text']
                    except:
                        pass
        
        # Discord limits to 4096 per embed description
        embed = discord.Embed(title="Wizard Analysis", description=full_text[:4096], color=WAYPOINT_BLUE)
        embed.set_footer(text="Orbit | Waypoint Analytical")
        await msg.edit(content=None, embed=embed)
    except Exception as e:
        await msg.edit(content=f"Wizard error: {str(e)}")

@orbit.command(name="edd")
async def edd(ctx, *, account: str):
    conn = get_db()
    acc = conn.execute("SELECT id, name FROM accounts WHERE name LIKE ?", (f"%{account}%",)).fetchone()
    if not acc:
        await ctx.send(f"Account '{account}' not found.")
        return
        
    edds = conn.execute("SELECT * FROM edd_submissions WHERE account_id=? ORDER BY submission_date DESC LIMIT 5", (acc['id'],)).fetchall()
    
    embed = discord.Embed(title=f"{acc['name']} — EDD Status", color=WAYPOINT_BLUE)
    for e in edds:
        emoji = "✅" if e['status'] == 'Accepted' else "⚠️"
        flags = e['field_flags']
        flags_text = f"Flags: {flags}" if flags and len(flags) > 2 else "No flags."
        embed.add_field(name=f"{emoji} {e['project_name']} ({e['format_type']})", value=f"Status: {e['status']} | Date: {e['submission_date']}\n{flags_text}", inline=False)
    if not edds:
        embed.description = "No EDD submissions found for this account."
    embed.set_footer(text="Orbit | Waypoint Analytical")
    await ctx.send(embed=embed)

if __name__ == '__main__':
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Error: DISCORD_BOT_TOKEN environment variable not set.")
