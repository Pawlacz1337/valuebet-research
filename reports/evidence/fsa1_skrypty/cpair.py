import warnings, csv; warnings.filterwarnings("ignore")
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    import selrep
cand = set(selrep.mine) | set(selrep.eng)
import recon
cps = recon.read("C")
bad_member = bad_match = bad_odds = 0; nlegs = 0; sizes = {}
for c in cps:
    sizes[len(c["legs"])] = sizes.get(len(c["legs"]), 0) + 1
    mids = [l[0] for l in c["legs"]]
    if len(set(mids)) != len(mids): bad_match += 1
    for (mid, mk, oc, ln, k, p) in c["legs"]:
        nlegs += 1
        if (mid, mk, oc) not in cand: bad_member += 1
        if len(c["legs"]) > 1 and k < 1.20: bad_odds += 1
print(f"C: kuponów {len(cps)}, rozmiary {sizes}, nóg {nlegs}; noga spoza kandydatów A (replika ∪ silnik): {bad_member}; dublet z tego samego meczu: {bad_match}; noga dubletu < 1.20: {bad_odds}")
