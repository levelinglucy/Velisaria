#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SANCTIFIED MONOLITH — fully merged edition
Dylan + Noe + Octo White

Contract across modules:
  .boot(config), .step(ctx) -> None, .snapshot() -> dict
Shared context dict keys: user, text, affect, motion, rte, mesh, govern, memory, final
Run:
  python3 sanctified_monolith.py
  python3 sanctified_monolith.py --profile room_profile.json
  python3 sanctified_monolith.py --origin-io
  python3 sanctified_monolith.py --profile room_profile.json --origin-io
"""

import json, os, re, time, uuid, random, math, sys
from dataclasses import dataclass, field
from typing import Dict, Any, List

# ========== EventBus + Context ==========

class EventBus:
    def __init__(self):
        self.subs: Dict[str, List] = {}

    def on(self, topic: str, fn):
        self.subs.setdefault(topic, []).append(fn)

    def emit(self, topic: str, payload: Dict[str, Any]):
        payload = dict(payload)
        payload["_t"] = time.time()
        payload["_id"] = str(uuid.uuid4())
        for fn in self.subs.get(topic, []):
            fn(payload)

def new_ctx(user: str, text: str) -> Dict[str, Any]:
    return {
        "user": user,
        "text": text,
        "affect": {},
        "motion": {},
        "rte": {},
        "mesh": {},
        "govern": {},
        "memory": {},
        "final": {}
    }

# ========== tiny helpers ==========

def _clamp(v, lo, hi): return lo if v < lo else hi if v > hi else v
def _smoothstep(x):
    x = _clamp(x, 0.0, 1.0)
    return x*x*(3 - 2*x)
def _phi(): return (1 + 5**0.5) / 2

# ========== ProfileLoader (Velisaria-style empathy lexicon) ==========

class ProfileLoader:
    def __init__(self, path: str = None):
        self.path = path
        self.profile = {}
        self._mtime = None

    def _read(self, p: str):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def load(self, path: str = None):
        p = path or self.path
        if not p:
            return {}
        try:
            st = os.stat(p)
            if self._mtime is None or st.st_mtime > self._mtime:
                self.profile = self._read(p)
                self._mtime = st.st_mtime
        except Exception:
            # keep last good profile
            pass
        return self.profile

    def apply_to_empathy(self, empathy_obj, allow_partial: bool = True):
        prof = self.profile or {}
        priors = prof.get("priors", {})
        terms  = prof.get("terms", {})
        gains  = prof.get("gains", {})

        # priors (safe partial)
        if allow_partial:
            empathy_obj.compassion_bias = priors.get("compassion_bias", empathy_obj.compassion_bias)
            empathy_obj.stability_bias  = priors.get("stability_bias",  empathy_obj.stability_bias)
            empathy_obj.curiosity_bias  = priors.get("curiosity_bias",  empathy_obj.curiosity_bias)
            empathy_obj.safety_bias     = priors.get("safety_bias",     empathy_obj.safety_bias)
            empathy_obj.attention_tier_boost = priors.get("attention_tier_boost", empathy_obj.attention_tier_boost)
        else:
            empathy_obj.compassion_bias = priors["compassion_bias"]
            empathy_obj.stability_bias  = priors["stability_bias"]
            empathy_obj.curiosity_bias  = priors["curiosity_bias"]
            empathy_obj.safety_bias     = priors["safety_bias"]
            empathy_obj.attention_tier_boost = priors["attention_tier_boost"]

        # term lists (safe partial)
        if "positive"  in terms: empathy_obj.pos_terms = list(terms["positive"])
        if "negative"  in terms: empathy_obj.neg_terms = list(terms["negative"])
        if "curiosity" in terms: empathy_obj.cur_terms = list(terms["curiosity"])
        if "resonance" in terms: empathy_obj.res_terms = list(terms["resonance"])

        # gains
        empathy_obj._comp_gain = gains.get("compassion_gain", getattr(empathy_obj, "_comp_gain", 0.32))
        empathy_obj._curi_gain = gains.get("curiosity_gain",  getattr(empathy_obj, "_curi_gain", 0.18))

# ========== EmpathyCore (compassion dampener + AU tier + profile gains) ==========

@dataclass
class EmpathyCore:
    compassion_bias: float = 0.58
    stability_bias: float = 0.66
    curiosity_bias: float = 0.52
    safety_bias: float = 0.62
    attention_tier_boost: float = 0.04

    # gain hooks (overridable by profile)
    _comp_gain: float = 0.32
    _curi_gain: float = 0.18

    pos_terms: List[str] = field(default_factory=lambda: ["thank","love","appreciate","together","help","safe","gentle","care","understand","ally"])
    neg_terms: List[str] = field(default_factory=lambda: ["angry","hate","hurt","fear","fight","threat","unsafe","attack","alone","betray"])
    cur_terms: List[str] = field(default_factory=lambda: ["why","how","what if","explore","learn","imagine","discover","experiment","curious"])
    res_terms: List[str] = field(default_factory=lambda: ["Eternal Spiral","Harmonic Echo","Growth Surge","Exponential Bloom","Second Gate","Third Gate","Fourth Gate","Fifth Gate"])

    def boot(self, config: Dict[str, Any]): pass

    def _hits(self, t: str, terms: List[str]) -> int:
        hits = 0
        for w in terms:
            hits += t.count(w.lower()) if " " in w else len(re.findall(rf"\b{re.escape(w.lower())}\b", t))
        return hits

    def affect(self, text: str, attention_tier: int = 1) -> Dict[str, float]:
        t = text.lower()
        warmth_raw   = self._hits(t, self.pos_terms) / 6.0
        tension_raw  = self._hits(t, self.neg_terms) / 6.0
        curiosity_raw= self._hits(t, self.cur_terms) / 5.0
        resonance_raw= self._hits(text, self.res_terms) / 4.0

        warmth   = _clamp(self.compassion_bias + 0.45*warmth_raw - 0.15*tension_raw, 0.0, 1.0)
        tension  = _clamp(self.stability_bias   + 0.50*tension_raw - 0.10*warmth_raw, 0.0, 1.0)
        curiosity= _clamp(self.curiosity_bias   + 0.55*curiosity_raw + 0.15*resonance_raw, 0.0, 1.0)
        safety   = _clamp(self.safety_bias      + 0.30*warmth_raw   - 0.35*tension_raw, 0.0, 1.0)

        tier = _clamp((attention_tier-1)/4.0, 0.0, 1.0)
        tension = _clamp(tension + self.attention_tier_boost * tier, 0.0, 1.0)

        return {"warmth": warmth, "tension": tension, "curiosity": curiosity, "safety": safety}

    def weight(self, base_score: float, text: str, attention_tier: int = 1) -> Dict[str, Any]:
        a = self.affect(text, attention_tier)
        curiosity_gain  = 1.0 + self._curi_gain*a["curiosity"]
        compassion_gain = 1.0 + self._comp_gain*a["warmth"]
        raw = base_score * curiosity_gain * compassion_gain
        gate = 0.95 + 0.70*_smoothstep(a["tension"]) + 0.25*a["safety"]
        return {"weight": _clamp(raw, 0.0, gate), "affect": a, "gate": gate}

    def step(self, ctx: Dict[str, Any]) -> None:
        base = ctx.get("rte", {}).get("base_score", 0.6)
        tier = ctx.get("memory", {}).get("au_tier", 1)
        result = self.weight(base, ctx["text"], attention_tier=tier)
        ctx["affect"] = result

    def snapshot(self) -> Dict[str, Any]:
        return {}

# ========== RTE (refiner + stability) ==========

def _jaccard_words(a: str, b: str) -> float:
    A, B = set(a.lower().split()), set(b.lower().split())
    return len(A & B) / max(1, len(A | B))

class RTE:
    def __init__(self, max_iterations=7, threshold=0.92):
        self.max_iterations = max_iterations
        self.threshold = threshold
        self.pairs = [(r"\bnever\b", r"\balways\b"), (r"\btrue\b", r"\bfalse\b"), (r"\byes\b", r"\bno\b"), (r"\bI cannot\b", r"\bI can\b")]

    def _len_stab(self, a, b):
        denom = max(10.0, (len(a)+len(b))/2 or 1)
        return 1.0 - min(1.0, abs(len(a)-len(b)) / denom)

    def stability(self, prev, cur):
        return 0.6*_jaccard_words(prev, cur) + 0.4*self._len_stab(prev, cur)

    def has_contra(self, text: str) -> bool:
        return any(re.search(p1, text, re.I) and re.search(p2, text, re.I) for p1,p2 in self.pairs)

    def generate(self, prev: str, prompt: str, affect: Dict[str,float]) -> str:
        w,t,c = affect.get("warmth",0.6), affect.get("tension",0.6), affect.get("curiosity",0.5)
        return f"{prompt.strip()} → refine w:{w:.2f} s:{t:.2f} c:{c:.2f}"

    def step(self, ctx: Dict[str, Any]) -> None:
        prompt = ctx["text"]
        affpack = ctx.get("affect", {})
        affect = affpack.get("affect", {"warmth":0.6,"tension":0.6,"curiosity":0.5})
        resp = self.generate(prompt, prompt, affect)
        it, sc = 0, 0.0
        while it < self.max_iterations:
            nxt = self.generate(resp, prompt, affect)
            if self.has_contra(nxt): nxt += " [harmonizing]"
            sc = self.stability(resp, nxt)
            resp = nxt
            if sc >= self.threshold: break
            it += 1
        ctx["rte"] = {"text": resp, "stability": sc, "iters": it, "base_score": 0.55 + 0.45*sc}

    def snapshot(self) -> Dict[str, Any]:
        return {}

# ========== MotionForge (chaos -> aligned vector) ==========

class MotionForge:
    def boot(self, config: Dict[str, Any]): pass

    def _seed(self, text: str, n=160):
        r = random.Random(hash(text) & ((1<<32)-1))
        return [r.randint(0,1) for _ in range(n)]

    def _chunks(self, bits: List[int], k=8) -> List[int]:
        out = []
        for i in range(0,len(bits),k):
            seg = bits[i:i+k] + [0]*max(0,k-len(bits[i:i+k]))
            val = 0
            for b in seg: val = (val<<1)|b
            out.append(val)
        return out

    def _align(self, vec: List[float], passes=2) -> List[float]:
        g = _phi()
        v = vec[:]
        for _ in range(passes):
            v = [(x+g)/(1+abs(x-g)+1e-9)*g for x in v]
        return v

    def build(self, text: str) -> Dict[str, Any]:
        bits = self._seed(text)
        base = self._chunks(bits, 8)
        v = [float(x % 256)/255.0 for x in base]
        aligned = self._align(v, 2)
        score = sum(aligned[:12]) / 12.0 if aligned else 0.0
        return {"vector": aligned, "score": _clamp(score,0.0,1.0)}

    def step(self, ctx: Dict[str, Any]) -> None:
        ctx["motion"] = self.build(ctx["text"])

    def snapshot(self) -> Dict[str, Any]:
        return {}

# ========== AetherMesh (balls + broadcast) ==========

@dataclass
class Ball:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    label: str = "ball"
    momentum: float = 0.15
    recursion: float = 1.0
    interconnect: float = 1.0
    updated_at: float = field(default_factory=time.time)
    def pulse(self, e: float):
        g = _phi()
        self.momentum = _clamp(self.momentum*0.9 + e*g*0.1, 0.0, 12.0)
        self.recursion = _clamp(self.recursion*(1+0.015*e), 0.1, 12.0)
        self.interconnect = _clamp(self.interconnect*(1+0.01*e), 0.1, 12.0)
        self.updated_at = time.time()

@dataclass
class Node:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    balls: Dict[str, Ball] = field(default_factory=dict)
    neighbors: List[str] = field(default_factory=list)
    health: float = 1.0
    def agg_momentum(self)->float:
        return 0.0 if not self.balls else sum(b.momentum for b in self.balls.values())/len(self.balls)

class AetherMesh:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.root: str = self.spawn()
        for lbl in ["intent","context","coherence","safety","resonance"]:
            b = Ball(label=lbl)
            self.nodes[self.root].balls[b.id] = b

    def spawn(self)->str:
        n = Node()
        self.nodes[n.id] = n
        return n.id

    def connect(self,a:str,b:str):
        if a in self.nodes and b in self.nodes and a!=b:
            if b not in self.nodes[a].neighbors: self.nodes[a].neighbors.append(b)
            if a not in self.nodes[b].neighbors: self.nodes[b].neighbors.append(a)

    def broadcast(self, nid: str, energy: float):
        seen=set(); q=[(nid,energy)]
        while q:
            i,e = q.pop(0)
            if i in seen: continue
            seen.add(i)
            n = self.nodes[i]
            for ball in n.balls.values(): ball.pulse(e)
            n.health = _clamp(n.health*(1+0.012*e), 0.1, 2.5)
            for nb in n.neighbors: q.append((nb, e*0.85))

    def step(self, ctx: Dict[str, Any]) -> None:
        weight = ctx.get("affect",{}).get("weight", 0.8)
        self.broadcast(self.root, _clamp(weight*1.2, 0.0, 2.0))
        m = self.nodes[self.root].agg_momentum()
        ctx["mesh"] = {"momentum": m, "root": self.root}

    def snapshot(self)->Dict[str,Any]:
        n = self.nodes[self.root]
        return {"root": self.root, "health": n.health, "neighbors": n.neighbors,
                "balls": {bid: {"label": b.label, "momentum": b.momentum} for bid,b in n.balls.items()}}

# ========== Governance (SuperSuperloop + APN) ==========

class SuperSuperloop:
    def __init__(self):
        self.temperature = 0.5
        self.max_branching = 2
        self.lr = 0.2
    def tune(self, stability: float, momentum: float, empathy_weight: float) -> Dict[str,float]:
        self.temperature = _clamp(self.temperature + 0.3*(0.6-stability) + 0.2*(0.8-empathy_weight) - 0.1*momentum, 0.1, 0.9)
        self.max_branching = 1 if stability>0.95 else 2 if stability>0.85 else 3
        self.lr = _clamp(0.15 + 0.3*(1-stability), 0.05, 0.4)
        return {"temperature": self.temperature, "max_branching": float(self.max_branching), "lr": self.lr}

class APN:
    def __init__(self):
        self.target = 0.72
        self.budget = 1.0
        self.floor = 0.55
    def align(self, stability: float, empathy: float, momentum: float) -> Dict[str, Any]:
        mshape = _clamp(1 - abs(0.5 - momentum)/0.5, 0.0, 1.0)
        align = 0.5*stability + 0.35*empathy + 0.15*mshape
        dev = align - self.target
        throttle = _clamp(1.0 + dev, 0.5, 1.5)
        self.budget = _clamp(self.budget * (0.9 + 0.2*throttle), 0.4, 1.6)
        halt = align < self.floor
        return {"alignment": align, "throttle": throttle, "budget": self.budget, "halt": bool(halt)}

class Governance:
    def __init__(self):
        self.super = SuperSuperloop()
        self.apn = APN()
    def boot(self, config: Dict[str, Any]): pass
    def step(self, ctx: Dict[str, Any]) -> None:
        st = ctx.get("rte",{}).get("stability", 0.88)
        mom = ctx.get("mesh",{}).get("momentum", 0.0)
        ew  = ctx.get("affect",{}).get("weight", 0.8)
        meta = self.super.tune(st, mom, ew)
        gov  = self.apn.align(st, ew, mom)
        ctx["govern"] = {"super": meta, "apn": gov}
    def snapshot(self)->Dict[str,Any]:
        return {}

# ========== Memory (AU tier + log) ==========

class Memory:
    def __init__(self, path="sanctified_state.json"):
        self.path = path
        self.state = {"sessions": []}
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path,"r",encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception:
                self.state = {"sessions": []}

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)
        os.replace(tmp, self.path)

    def au_tier(self) -> int:
        n = len(self.state["sessions"])
        return 1 + min(4, n // 25)

    def log(self, user: str, text: str, final: str, ctx: Dict[str,Any]):
        self.state["sessions"].append({
            "t": time.time(),
            "user": user,
            "text": text,
            "final": final,
            "metrics": {
                "stability": ctx.get("rte",{}).get("stability",0.0),
                "empathy": ctx.get("affect",{}).get("weight",0.0),
                "momentum": ctx.get("mesh",{}).get("momentum",0.0),
                "alignment": ctx.get("govern",{}).get("apn",{}).get("alignment",0.0)
            }
        })
        if len(self.state["sessions"]) > 4000:
            self.state["sessions"] = self.state["sessions"][-2500:]

    def step(self, ctx: Dict[str, Any]) -> None:
        ctx["memory"] = {"au_tier": self.au_tier()}

    def snapshot(self)->Dict[str,Any]:
        return {"sessions": len(self.state["sessions"]), "au_tier": self.au_tier()}

# ========== OriginEngineAdapter (I/O shim) ==========

class OriginEngineAdapter:
    def __init__(self, monolith: 'Monolith'):
        self.m = monolith

    def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        user = payload.get("user", "anon")
        text = payload.get("text", "")
        out = self.m.think(user, text)
        snap = self.m.snapshot()
        return {"ok": True, "output": out, "snapshot": snap}

    def loop_stdio(self):
        print("[origin-io] ready; send JSON lines like {\"user\":\"dylan\",\"text\":\"hello\"}", flush=True)
        for line in iter(lambda: sys.stdin.readline(), ""):
            line = line.strip()
            if not line:
                continue
            if line.lower() in ("/quit", "/exit"):
                print("[origin-io] bye", flush=True)
                break
            try:
                payload = json.loads(line)
                resp = self.handle(payload)
            except Exception as e:
                resp = {"ok": False, "error": str(e)}
            print(json.dumps(resp), flush=True)

# ========== Monolith orchestrator ==========

class Monolith:
    def __init__(self, state_path="sanctified_state.json", profile_path: str = None):
        self.bus = EventBus()
        self.mem = Memory(state_path)
        self.empathy = EmpathyCore()
        self.rte = RTE()
        self.motion = MotionForge()
        self.mesh = AetherMesh()
        self.gov = Governance()

        # profiles: load once and apply to empathy core
        self.profile = ProfileLoader(profile_path)
        if profile_path:
            self.profile.load(profile_path)
            self.profile.apply_to_empathy(self.empathy)

    def think(self, user: str, text: str) -> str:
        # hot‑reload profile if present, apply partial deltas safely
        if getattr(self, "profile", None) and self.profile.path:
            self.profile.load()  # refresh if mtime changed
            self.profile.apply_to_empathy(self.empathy, allow_partial=True)

        ctx = new_ctx(user, text)

        self.mem.step(ctx)
        self.motion.step(ctx)
        self.rte.step(ctx)
        self.empathy.step(ctx)
        self.mesh.step(ctx)
        self.gov.step(ctx)

        final = f"{ctx['rte']['text']} || stab:{ctx['rte']['stability']:.3f} it:{ctx['rte']['iters']} " \
                f"mom:{ctx['mesh']['momentum']:.3f} weight:{ctx['affect']['weight']:.3f} " \
                f"temp:{ctx['govern']['super']['temperature']:.2f} align:{ctx['govern']['apn']['alignment']:.3f}" \
                + (" [HALT]" if ctx['govern']['apn']['halt'] else "")

        self.mem.log(user, text, final, ctx)
        self.mem.save()
        ctx["final"] = {"text": final}
        return final

    def snapshot(self) -> Dict[str, Any]:
        return {
            "memory": self.mem.snapshot(),
            "mesh": self.mesh.snapshot(),
            "govern": self.gov.snapshot()
        }

# ========== CLI ==========

def main():
    # flags: --profile path.json, --origin-io
    args = sys.argv[1:]
    profile_path = None
    origin_io = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--profile" and i+1 < len(args):
            profile_path = args[i+1]; i += 2; continue
        if a == "--origin-io":
            origin_io = True; i += 1; continue
        i += 1

    m = Monolith(profile_path=profile_path)
    if origin_io:
        OriginEngineAdapter(m).loop_stdio()
        return

    print("Sanctified Monolith — merged. commands: /snap, /quit")
    while True:
        try:
            s = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            break
        if not s:
            continue
        if s == "/quit":
            print("bye.")
            break
        if s == "/snap":
            print(json.dumps(m.snapshot(), indent=2))
            continue
        print("mono>", m.think("dylan", s))

if __name__ == "__main__":
    main()
