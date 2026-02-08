import json
import socket
import struct
import time
import asyncio
import httpx

ACTIVITY = {0: "offline", 1: "online", 2: "busy", 3: "away", 4: "snooze", 5: "looking to trade", 6: "looking to play"}
VISIBILITY = {1: "private", 2: "friends only", 3: "public"}

MSQ_FILTERS = "appid\\440\\empty\\1\\gametype\\valve,hidden"

STEAM_MSQ_ENDPOINT = "https://api.steampowered.com/IGameServersService/GetServerList/v1/"
STEAM_A2S_ENDPOINT = "https://api.steampowered.com/IGameServersService/QueryByFakeIP/v1/"

CONCURRENCY = 25

def get_apikey():
    return "REMOVED FOR PRIVACY REASONS"

def log(string):
    print(string)

def ip_to_int(addr):
    return struct.unpack("!I", socket.inet_aton(addr))[0]

def int_to_ip(addr):
    return socket.inet_ntoa(struct.pack("!I", addr))

state = {
    "async_client": None,
    "client": None
}

async def get_player_summaries(client, sid):
    url = (
        "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
        f"?key={get_apikey()}&steamids={sid}"
    )
    while True:
        r = await client.get(url)
        if r.status_code == 429:
            await asyncio.sleep(3)
            continue
        return r.json()


async def get_valve_fake_ip_players(client, address, appid=440):
    addr, port = address.split(":")
    url = (
        f"{STEAM_A2S_ENDPOINT}?key={get_apikey()}"
        f"&fake_ip={ip_to_int(addr)}&fake_port={port}"
        f"&app_id={appid}&query_type=2"
    )

    while True:
        r = await client.get(url)
        if r.status_code == 429:
            await asyncio.sleep(2)
            continue
        data = r.json()
        return data.get("response", {}).get("players_data", {}).get("players", [])


async def get_all_valve_servers(client):
    while True:
        r = await client.get(
            f"{STEAM_MSQ_ENDPOINT}?key={get_apikey()}&limit=20000&filter={MSQ_FILTERS}"
        )
        if r.status_code == 429:
            await asyncio.sleep(3)
            continue

        return r.json().get("response", {}).get("servers", [])


async def scan_server(semaphore, client, target_sid, target_map, server):
    async with semaphore:
        address = server.get("addr")
        if not address:
            return None
        try:
            players = await get_valve_fake_ip_players(client, address)
            for p in players:
                if str(p.get("name")) == target_sid:
                    if target_map != "" and str(server.get("map")).__contains__(target_map):
                        print(server.get("name"))
                        return address
                    else:
                        print(server.get("name"))
                        return address
        except Exception:
            pass

    return None


async def main():
    target_sid = input("Enter Steam name to search for: ").strip()
    target_map = input("Enter possible map to look for: ").strip()

    async with httpx.AsyncClient(timeout=20) as client:
        servers = await get_all_valve_servers(client)
        print(f"Found {len(servers)} servers to scan...")

        sem = asyncio.Semaphore(CONCURRENCY)

        tasks = [
            scan_server(sem, client, target_sid, target_map, server)
            for server in servers
        ]

        results = await asyncio.gather(*tasks)

    found = [addr for addr in results if addr]
    if found:
        print(f"Steam name {target_sid} found on {len(found)} servers:")
        for a in found:
            print(" -", a)
    else:
        print(f"Steam name {target_sid} not found on any server.")


if __name__ == "__main__":
    asyncio.run(main())