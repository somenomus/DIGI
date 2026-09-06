"""run before a training job. deletes finished/aborted RL_ep* sims to free
stored slots (cap is 20). the env cleans up its own sims but only knows about
the current process, so leftovers from earlier jobs pile up. keeps a small
whitelist. training sims are worthless once their data is in the buffer.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "openlab"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg
import openlab

# keep these, email links and the eval baselines
KEEP_NAMES = {
    "RL_ep1_133307",  # MSE 0.5x reference sim, linked from an email
    "RL_ep1_80586",   # MSE 1.6x reference sim, linked from an email
    "RL_ep1_444572",  # realistic 0.2x eval
    "RL_ep1_157180",  # realistic 0.4x eval
    "RL_ep1_639141",  # realistic 1.0x eval
}
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
    print(f"[prune] stored sims before: {len(sims)}")
    deleted = 0
    for s in sims:
        name = s.get("Name", "")
        sid = s.get("SimulationID", "")
        status = s.get("Status", "")
        if name in KEEP_NAMES or sid in KEEP_IDS:
            continue
        if not name.startswith("RL_ep"):
            continue
        if status in ("Running", "Created"):
            continue  # never touch a live sim
        try:
            sess.delete_simulation(sid)
            deleted += 1
        except Exception:
            pass
    print(f"[prune] deleted {deleted}; stored sims now: {len(sess.simulations())}")


if __name__ == "__main__":
    main()
