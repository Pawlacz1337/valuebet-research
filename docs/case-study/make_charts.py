import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
OUT="docs/case-study/"
SURF="#ffffff"; INK="#111111"; INK2="#55544f"; MUTED="#8a8984"; GRID="#ecebe7"
BLUE="#2a78d6"; BLUE_L="#b7d3f6"; RED="#e34948"; RED_L="#f6c9c8"; GRAY="#c9c8c2"
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":15,"figure.facecolor":SURF,"axes.facecolor":SURF})
SRC="Source: valuebet-research · official backtest run 4599dca, audited · 51,653 matches, 22 leagues, 2019/20–2025/26"

def header(fig,title,sub):
    fig.text(0.04,0.945,title,fontsize=26,fontweight="bold",color=INK,va="top")
    fig.text(0.04,0.875,sub,fontsize=15,color=INK2,va="top")
def footer(fig,extra=""):
    fig.text(0.04,0.03,SRC+(("\n"+extra) if extra else ""),fontsize=10.5,color=MUTED,va="bottom")
def clean(ax):
    for s in ax.spines.values(): s.set_visible(False)
    ax.tick_params(length=0)

def rbar_h(ax,y,x0,x1,h,color,r=0.12):
    lo,hi=min(x0,x1),max(x0,x1)
    ax.add_patch(FancyBboxPatch((lo,y-h/2),hi-lo,h,boxstyle=f"round,pad=0,rounding_size={r}",
        mutation_aspect=1/ (ax.get_data_ratio() if False else 1),fc=color,ec="none"))

# ---------- 2. CLV by strategy: bars + CI whiskers ----------
fig=plt.figure(figsize=(16,10),dpi=120)
ax=fig.add_axes([0.30,0.17,0.66,0.62])
st=[("A","best of Bet365 / Bwin",1.97,1.52,2.42,2628,BLUE),
    ("A · power de-vig","robustness check, same bets",1.52,1.05,1.98,2628,BLUE),
    ("A3","best of 3 (+ William Hill)",2.65,2.19,3.12,3146,BLUE),
    ("B365","single bookmaker",1.54,1.04,2.02,2461,BLUE),
    ("D","= A under the 12% stake tax",-10.27,-10.67,-9.87,2628,RED)]
ys=[5.2,4.2,3.2,2.2,0.6]
ax.set_xlim(-12.5,5.2); ax.set_ylim(-0.2,5.9)
for x in [-10,-8,-6,-4,-2,2,4]: ax.axvline(x,color=GRID,lw=1,zorder=0)
ax.axvline(0,color=INK2,lw=1.6,zorder=1)
ax.axhline(1.4,xmin=0,xmax=1,color=GRID,lw=1.2,ls=(0,(3,3)))
for (name,desc,m,lo,hi,n,c),y in zip(st,ys):
    ax.barh(y,m,height=0.56,color=c,zorder=2)
    ax.plot([lo,hi],[y,y],color=INK,lw=2,zorder=3); 
    for e in (lo,hi): ax.plot([e,e],[y-0.12,y+0.12],color=INK,lw=2,zorder=3)
    if m>0:
        ax.text(hi+0.18,y,f"{m:+.2f}%",va="center",fontsize=18,fontweight="bold",color=INK)
    else:
        ax.text(0.2,y,f"−{abs(m):.2f}%",va="center",fontsize=18,fontweight="bold",color=RED)
    ax.text(-0.02,y+0.06,name,transform=ax.get_yaxis_transform(),ha="right",va="bottom",fontsize=17,fontweight="bold",color=INK)
    ax.text(-0.02,y-0.04,desc,transform=ax.get_yaxis_transform(),ha="right",va="top",fontsize=13,color=INK2)
ax.text(-12.3,1.12,"0.88 × 1.0197 − 1 = −10.27%   ← the tax alone turns the edge into a loss",fontsize=14,color=RED,va="center")
ax.set_yticks([]); ax.set_xticks([-10,-8,-6,-4,-2,0,2,4])
ax.set_xticklabels([(f"+{v}%" if v>0 else f"−{abs(v)}%") if v else "0" for v in [-10,-8,-6,-4,-2,0,2,4]],color=INK2,fontsize=13)
ax.set_xlabel("CLV vs Pinnacle closing price  ·  bar = mean, whiskers = 95% CI (cluster bootstrap)",color=INK2,fontsize=13,labelpad=12)
clean(ax)
header(fig,"The edge is real but thin — the 12% tax wipes it out",
       "Every untaxed variant beats the closing price by ~1.5–2.7%, with the 95% CI above zero. The same bets under Poland's stake tax lose ~10%.")
footer(fig,"n = 2,628 (A, D) · 3,146 (A3) · 2,461 (B365) bets · clusters = ISO weeks")
fig.savefig(OUT+"2_clv_by_strategy.png"); plt.close(fig)

# ---------- 3. CLV by season ----------
fig=plt.figure(figsize=(16,10),dpi=120)
ax=fig.add_axes([0.07,0.20,0.90,0.58])
se=["2019/20","2020/21","2021/22","2022/23","2023/24","2024/25","2025/26*"]
cl=[2.60,2.90,1.36,2.59,1.07,0.97,0.02]; nn=[622,451,527,377,355,186,110]
for i,(v,n) in enumerate(zip(cl,nn)):
    last=i==6
    ax.bar(i,v if not last else 0.04,width=0.64,color=BLUE if not last else GRAY,zorder=2)
    ax.text(i,v+0.08,f"{v:+.2f}%",ha="center",va="bottom",fontsize=19,fontweight="bold",color=INK if not last else MUTED)
for y in [1,2,3]: ax.axhline(y,color=GRID,lw=1,zorder=0)
ax.axhline(0,color=INK2,lw=1.4,zorder=3)
ax.plot([-0.45,6.45],[1.97,1.97],color=INK2,lw=1.5,ls=(0,(5,4)),zorder=4)
ax.text(6.45,2.03,"7-season average +1.97%",ha="right",va="bottom",fontsize=13,color=INK2)
ax.set_xticks(range(7)); ax.set_xticklabels([f"{s}\n{n} bets" for s,n in zip(se,nn)],fontsize=14,color=INK)
for lab in ax.get_xticklabels(): lab.set_linespacing(1.6)
ax.set_yticks([0,1,2,3]); ax.set_yticklabels(["0","+1%","+2%","+3%"],color=INK2,fontsize=13)
ax.set_ylim(0,3.55); ax.set_xlim(-0.6,6.6); clean(ax); ax.tick_params(axis="x",pad=10)
header(fig,"The edge is shrinking: strategy A's CLV by season",
       "From ~2.6–2.9% in 2019–21 to ~1% in 2023–25, on far fewer qualifying bets.")
footer(fig,"*2025/26 not comparable: Pinnacle odds disappear from football-data from Nov 2025 (38% coverage).")
fig.savefig(OUT+"3_clv_by_season.png"); plt.close(fig)
print("ok")

# ---------- 1. illusion vs edge (v2 style) ----------
ORANGE="#eb6834"
fig=plt.figure(figsize=(16,10),dpi=120)
ax=fig.add_axes([0.30,0.17,0.66,0.62])
rows=[("Backtest A3","compounded, raw",0,27.2,"hatch","27%"),
      ("Backtest A","compounded, raw",0,14.0,"hatch","14%"),
      ("Lab · A3","edge-supported, no tax",0,11.3,BLUE,"~11%"),
      ("Lab · A","edge-supported, no tax",0,5.7,BLUE,"~5.7%"),
      ("Poland","12% stake tax, 1 venue",1,3,ORANGE,"~1–3%")]
ys=[5.2,4.2,3.0,2.0,0.6]
ax.set_xlim(0,31); ax.set_ylim(-0.2,5.9)
for x in [5,10,15,20,25,30]: ax.axvline(x,color=GRID,lw=1,zorder=0)
for (name,desc,lo,hi,c,txt),y in zip(rows,ys):
    if c=="hatch":
        ax.barh(y,hi-lo,left=lo,height=0.56,color="#e4e3de",hatch="///",edgecolor="#a9a8a2",linewidth=0,zorder=2)
    else:
        ax.barh(y,hi-lo,left=lo,height=0.56,color=c,zorder=2)
    ax.text(hi+0.4,y,txt,va="center",fontsize=19,fontweight="bold",color=MUTED if c=="hatch" else INK)
    ax.text(-0.02,y+0.06,name,transform=ax.get_yaxis_transform(),ha="right",va="bottom",fontsize=17,fontweight="bold",color=INK)
    ax.text(-0.02,y-0.04,desc,transform=ax.get_yaxis_transform(),ha="right",va="top",fontsize=13,color=INK2)
ax.text(19.2,4.2,"mostly luck + compounding:\nnot reported as a result",fontsize=13,color=INK2,va="center")
ax.axvline(0,color=INK2,lw=1.4,zorder=3)
ax.set_yticks([]); ax.set_xticks([0,5,10,15,20,25,30]); ax.set_xticklabels(["0","5%","10%","15%","20%","25%","30%"],color=INK2,fontsize=13)
ax.set_xlabel("Return on capital per year",color=INK2,fontsize=13,labelpad=12)
clean(ax)
header(fig,"The backtest said 14–27% a year. The edge supports far less.",
       "Lab = Σ(stake share × CLV): no tax, best of 3 bookmakers without a Polish licence, no account limits.")
footer(fig,"Poland figure: in-sample estimate before account limits.")
fig.savefig(OUT+"1_illusion_vs_edge.png"); plt.close(fig)
print("ok1")
