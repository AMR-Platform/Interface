"""
barrier_ws_server.py – v9-fixed
• LiDAR → occupancy (FREE carving, OCC stamping)
• obstacle inflation before A*  ⇒  path always fits
• pure-pursuit follower, auto re-plan, manual override
• transmits remaining path for UI overlay
"""

import asyncio, json, math, time, base64, random, heapq
import numpy as np, websockets

# ── geometry & static map ──────────────────────────────────────
RES, W, H = 0.10, 200, 100               # 20 m × 10 m grid
UNKNOWN, FREE, OCC = 0, 1, 255
GRID = np.zeros((H, W), np.uint8)
GRID[0,:]=GRID[-1,:]=GRID[:,0]=GRID[:,-1]=OCC
for x in range(30, W-30, 40): GRID[10:H-10, x:x+3] = OCC       # shelves
rng=np.random.default_rng(42)
for _ in range(12):                                             # pallets
    rx,ry=rng.integers(35,W-35), rng.integers(15,H-15)
    GRID[ry-5:ry+5, rx-5:rx+5] = OCC
STATIC_B64 = base64.b64encode(GRID.tobytes()).decode()

# LiDAR
MAX_R, ANG0, INC, N_BEAMS = 10.0, -135, 1.0, 271

# robot
RADIUS, BASE = 0.05, 0.30
BODY_RAD     = 0.18
R_CELLS      = int(BODY_RAD/RES)

# state
x,y,yaw = 2.0, 2.0, 0.0
battery, seq = 100.0, 0
mode   = "auto"
goal   = None
manual_v = manual_w = 0.0
path, pi = [], 0

# ── helpers ───────────────────────────────────────────────────
def wheel_rpm(v,w):
    vr,vl = v+w*BASE/2, v-w*BASE/2
    return [(vr/(2*math.pi*RADIUS))*60, (vl/(2*math.pi*RADIUS))*60]

def ray(px,py,ang):
    for r in np.arange(0, MAX_R, RES/2):
        gx,gy=int((px+r*math.cos(ang))/RES), int((py+r*math.sin(ang))/RES)
        if gx<0 or gx>=W or gy<0 or gy>=H or GRID[gy,gx]==OCC:
            return r
    return MAX_R

def lidar():
    a0=math.radians(ANG0)
    return [ray(x,y,a0+i*math.radians(INC)+yaw) for i in range(N_BEAMS)]

def update_grid(scan):
    a0=math.radians(ANG0)
    for i,r in enumerate(scan):
        ang=a0+i*math.radians(INC)+yaw
        for d in np.arange(0, min(r,MAX_R), RES/2):
            gx,gy=int((x+d*math.cos(ang))/RES), int((y+d*math.sin(ang))/RES)
            if 0<=gx<W and 0<=gy<H and GRID[gy,gx]!=OCC:
                GRID[gy,gx]=FREE
        if r<MAX_R:
            hx,hy=int((x+r*math.cos(ang))/RES), int((y+r*math.sin(ang))/RES)
            if 0<=hx<W and 0<=hy<H: GRID[hy,hx]=OCC

def blocked(cx,cy):
    for dy in range(-R_CELLS,R_CELLS+1):
        for dx in range(-R_CELLS,R_CELLS+1):
            if dx*dx+dy*dy>R_CELLS*R_CELLS: continue
            nx,ny=cx+dx, cy+dy
            if 0<=nx<W and 0<=ny<H and GRID[ny,nx]==OCC:
                return True
    return False

def occupied(px,py):                     # run-time footprint check
    return blocked(int(px/RES), int(py/RES))

def astar(start_xy,goal_xy):
    sx,sy=int(start_xy[0]/RES), int(start_xy[1]/RES)
    gx,gy=int(goal_xy[0]/RES) , int(goal_xy[1]/RES)
    h=lambda n: abs(n[0]-gx)+abs(n[1]-gy)
    OPEN=[(h((sx,sy)),0,(sx,sy),None)]
    came,cost={}, {(sx,sy):0}
    dirs=[(1,0),(-1,0),(0,1),(0,-1)]
    while OPEN:
        _,g,n,par=heapq.heappop(OPEN)
        if n in came: continue
        came[n]=par
        if n==(gx,gy): break
        for dx,dy in dirs:
            nb=(n[0]+dx,n[1]+dy)
            if not(0<=nb[0]<W and 0<=nb[1]<H): continue
            if blocked(*nb): continue
            ng=g+1
            if ng<cost.get(nb,1e9):
                cost[nb]=ng
                heapq.heappush(OPEN,(ng+h(nb),ng,nb,n))
    if (gx,gy) not in came: return []
    pts=[]
    n=(gx,gy)
    while n:
        pts.append((n[0]*RES+RES/2, n[1]*RES+RES/2)); n=came[n]
    return pts[::-1]

def pursue(tgt):
    dx,dy=tgt[0]-x, tgt[1]-y
    ang=math.atan2(dy,dx)
    err=((ang-yaw+math.pi)%(2*math.pi))-math.pi
    w=1.4*err; v=0.6*max(0,1-abs(err))
    return v,w

# ── 0.1 s update ───────────────────────────────────────────────
def step(dt=0.1):
    global x,y,yaw,battery,seq,path,pi
    scan=lidar(); update_grid(scan)

    if mode=="manual":
        v,w=manual_v,manual_w
    else:
        if goal and (not path or pi>=len(path)-1):
            path,pi=astar((x,y),goal),0
        if path and any(blocked(int(px/RES),int(py/RES))
                        for px,py in path[pi:pi+3]):
            path,pi=astar((x,y),goal),0
        if not path: v=w=0.0
        else:
            tgt=path[pi]
            if math.hypot(tgt[0]-x,tgt[1]-y)<0.25 and pi<len(path)-1:
                pi+=1; tgt=path[pi]
            v,w=pursue(tgt)

    nx,ny=x+v*math.cos(yaw)*dt, y+v*math.sin(yaw)*dt
    if occupied(nx,ny): v,nx,ny=0.0,x,y
    yaw=(yaw+w*dt+math.pi)%(2*math.pi)-math.pi
    x,y=nx,ny
    battery=max(0,battery-0.002); seq+=1
    return v,w,scan,path[pi:] if path else []

# ── websocket stuff ────────────────────────────────────────────
CLIENTS=set()
async def handler(ws):
    global mode,manual_v,manual_w,goal
    CLIENTS.add(ws)
    try:
        async for txt in ws:
            d=json.loads(txt)
            if d.get("type")=="mode":      mode=d["mode"]
            elif d.get("type")=="cmd_vel": manual_v,manual_w=d["v"],d["w"]
            elif d.get("type")=="goal":    goal=(d["x"],d["y"]); mode="auto"
    finally:
        CLIENTS.remove(ws)

async def telemetry_loop():
    while True:
        if CLIENTS:
            v,w,scan,rem=step()
            pkt={
                "type":"telemetry","seq":seq,"ts":int(time.time()*1000),
                "pose":{"x":round(x,2),"y":round(y,2),
                        "yaw":round(math.degrees(yaw),1)},
                "battery":round(battery,1),
                "enc_rpm":[round(r,1) for r in wheel_rpm(v,w)],
                "scan":{"angle_min":ANG0,"angle_inc":INC,"ranges":scan},
                "path":rem,
                "grid":{"w":W,"h":H,"data":STATIC_B64}
            }
            await asyncio.gather(*[c.send(json.dumps(pkt)) for c in CLIENTS])
        await asyncio.sleep(0.1)

async def main():
    async with websockets.serve(handler, "", 8765):
        await telemetry_loop()

if __name__ == "__main__":
    asyncio.run(main())
