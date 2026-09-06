"""delete old stored sims on openlab, the cap is 20 now. keeps the KEEP_RECENT
newest plus a whitelist (sims linked from emails, the latest realistic ones).
everything we need from them is already cached locally. irreversible, run it
on purpose.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "openlab"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg
import openlab

KEEP_RECENT = 10
# keep these, theyre linked from emails, plus the latest realistic eval sims
KEEP_NAMES = {
    "RL_ep1_133307",  # MSE 0.5x reference sim, linked from an email
    "RL_ep1_80586",   # MSE 1.6x reference sim, linked from an email
    "RL_ep1_444572",  # realistic 0.2x (latest)
    "RL_ep1_157180",  # realistic 0.4x (latest)
    "RL_ep1_639141",  # realistic 1.0x (latest)
}
# and these ids, same reason
KEEP_IDS = {
    "cbfcdcf8-5adc-41ef-a47a-d893ca9fc4a8",
    "c1f3ef7a-5fe6-48e6-8e8e-29f88d86c661",
}


def main():
    openlab.login.switch_user(new_user=cfg.OPENLAB_EMAIL, new_key=cfg.OPENLAB_API_KEY,
                              new_licenseguid=cfg.OPENLAB_LICENSE_GUID, environment="prod")
    sess = openlab.http_client(username=cfg.OPENLAB_EMAIL, apikey=cfg.OPENLAB_API_KEY,
                               licenseguid=cfg.OPENLAB_LICENSE_GUID)
    sims = sess.simulations()
    print(f"Total stored sims: {len(sims)}")

    # newest first if the api gives a date, else listing order
    def keyfn(s):
        return s.get("LastUpdatedDate") or s.get("CreationDate") or ""
    has_dates = any(keyfn(s) for s in sims)
    ordered = sorted(sims, key=keyfn, reverse=True) if has_dates else sims
    print(f"Ordering by {'date' if has_dates else 'listing order (no dates)'}")

    keep, delete = [], []
    for i, s in enumerate(ordered):
        name = s.get("Name", "")
        sid = s.get("SimulationID", "")
        if i < KEEP_RECENT or name in KEEP_NAMES or sid in KEEP_IDS:
            keep.append(s)
        else:
            delete.append(s)

    print(f"\nKeeping {len(keep)} sims:")
    for s in keep:
        print(f"  KEEP  {s.get('Name'):22s} {s.get('ConfigurationName','')}")
    print(f"\nDeleting {len(delete)} sims...")

    ok, fail = 0, 0
    for s in delete:
        try:
            sess.delete_simulation(s["SimulationID"])
            ok += 1
            if ok % 50 == 0:
                print(f"  deleted {ok}/{len(delete)}...")
        except Exception as e:
            fail += 1
    print(f"\nDeleted {ok}, failed {fail}.")

    remaining = sess.simulations()
    print(f"Remaining stored sims: {len(remaining)}")


if __name__ == "__main__":
    main()
