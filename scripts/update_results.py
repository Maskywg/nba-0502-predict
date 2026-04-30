import requests

# 台灣 5/2 的比賽 = 美國東部 5/1 → GAME_DATE = "20260501"
GAME_DATE = "20260501"

ESPN_URL = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={GAME_DATE}&seasontype=3"

TEAM_MAP = {
    "Orlando Magic": "魔術",
    "Detroit Pistons": "活塞",
    "Cleveland Cavaliers": "騎士",
    "Toronto Raptors": "暴龍",
    "Los Angeles Lakers": "湖人",
    "Houston Rockets": "火箭",
    "Oklahoma City Thunder": "雷霆",
    "Phoenix Suns": "太陽",
    "Boston Celtics": "塞爾提克",
    "Philadelphia 76ers": "76人",
    "New York Knicks": "尼克",
    "Atlanta Hawks": "老鷹",
    "Minnesota Timberwolves": "灰狼",
    "Denver Nuggets": "金塊",
    "San Antonio Spurs": "馬刺",
    "Portland Trail Blazers": "拓荒者",
}

# MATCHES 的 key = match id (0,1,2)
# a = Team A（第一隊，客場）, b = Team B（第二隊，主場）
# 對應 Firestore 欄位: r{id}=勝隊, a{id}=A隊分數, b{id}=B隊分數, m{id}=勝分差距
MATCHES = {
    0: ("活塞", "魔術"),   # DET @ ORL G6
    1: ("騎士", "暴龍"),   # CLE @ TOR G6
    2: ("湖人", "火箭"),   # LAL @ HOU G6
}

FIRESTORE_URL = (
    "https://firestore.googleapis.com/v1/projects/"
    "gen-lang-client-0737444461/databases/(default)/"
    "documents/game_results/nba_0502"
)

def margin_bucket(diff):
    """將分差轉換為 0/1/2（對應 ≤10 / 11-20 / 21+）"""
    if diff <= 10:
        return 0
    elif diff <= 20:
        return 1
    else:
        return 2

def get_result(event):
    if event["status"]["type"]["name"] != "STATUS_FINAL":
        return None, None, None
    comps = event["competitions"][0]["competitors"]
    winner = None
    score_map = {}
    for comp in comps:
        team_name = TEAM_MAP.get(comp["team"]["displayName"])
        score_map[team_name] = int(comp.get("score", 0))
        if comp.get("winner", False):
            winner = team_name
    return winner, score_map, comps

def main():
    data = requests.get(ESPN_URL, timeout=10).json()
    results = {i: {"winner": None, "scoreA": None, "scoreB": None, "margin": None} for i in range(3)}

    for event in data.get("events", []):
        comps = event["competitions"][0]["competitors"]
        team_names = {TEAM_MAP.get(c["team"]["displayName"]) for c in comps}

        for mid, (teamA, teamB) in MATCHES.items():
            if team_names == {teamA, teamB}:
                winner, score_map, _ = get_result(event)
                if winner and score_map:
                    sA = score_map.get(teamA, 0)
                    sB = score_map.get(teamB, 0)
                    diff = abs(sA - sB)
                    results[mid] = {
                        "winner": winner,
                        "scoreA": sA,
                        "scoreB": sB,
                        "margin": margin_bucket(diff)
                    }
                break

    print("📊 賽果:", results)

    fields = {}
    mask_parts = []
    for i in range(3):
        r = results[i]
        fields[f"r{i}"] = {"stringValue": r["winner"]} if r["winner"] else {"nullValue": None}
        fields[f"a{i}"] = {"integerValue": str(r["scoreA"])} if r["scoreA"] is not None else {"nullValue": None}
        fields[f"b{i}"] = {"integerValue": str(r["scoreB"])} if r["scoreB"] is not None else {"nullValue": None}
        fields[f"m{i}"] = {"integerValue": str(r["margin"])} if r["margin"] is not None else {"nullValue": None}
        mask_parts += [f"r{i}", f"a{i}", f"b{i}", f"m{i}"]

    mask = "&".join(f"updateMask.fieldPaths={p}" for p in mask_parts)
    resp = requests.patch(f"{FIRESTORE_URL}?{mask}", json={"fields": fields}, timeout=10)
    if resp.status_code == 200:
        print("✅ Firestore 更新成功")
    else:
        print(f"❌ 更新失敗 {resp.status_code}: {resp.text}")

if __name__ == "__main__":
    main()
