"""make the 'drill_mixed' config on openlab.

one case where the formation changes a lot inside a single episode instead
of every layer being scaled the same way:

  0-5 m drilled  (MD 2497-2502): 12 MPa  soft, ~0.2x the realistic base
  5-7 m          (MD 2502-2504): 30 MPa  moderate, ~0.5x
  7-11 m         (MD 2504-2508): 65 MPa  hard, ~1.0x

each layer on its own is inside the trained range (10-70 MPa), only the
contrast within one episode is new. other configs untouched.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "openlab"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg
import openlab

NEW_NAME = "drill_mixed"
# (MD, UCS in Pa), each entry sets UCS from that MD down
PROFILE = [
    (0,    12_000_000),   # soft   (covers bit start 2497 -> 2502)
    (2502, 30_000_000),   # moderate
    (2504, 65_000_000),   # hard (to target 2508 and beyond)
]


def main():
    openlab.login.switch_user(new_user=cfg.OPENLAB_EMAIL, new_key=cfg.OPENLAB_API_KEY,
                              new_licenseguid=cfg.OPENLAB_LICENSE_GUID, environment="prod")
    sess = openlab.http_client(username=cfg.OPENLAB_EMAIL, apikey=cfg.OPENLAB_API_KEY,
                               licenseguid=cfg.OPENLAB_LICENSE_GUID)
    configs = sess.configurations()
    if any(c.get("Name") == NEW_NAME for c in configs):
        print(f"Config '{NEW_NAME}' already exists — skipping.")
        return

    base = [c for c in configs if c.get("Name") == cfg.CONFIG_NAME]
    if not base:
        print(f"ERROR: base config '{cfg.CONFIG_NAME}' not found."); return
    base_id = base[0].get("ConfigurationID") or base[0].get("Id")
    data = sess.configuration_data(base_id)

    fric = data["FormationStrength"][0].get("InternalFrictionAngle", 0.5236)
    data["FormationStrength"] = [
        {"MD": md, "UCS": ucs, "InternalFrictionAngle": fric} for md, ucs in PROFILE
    ]
    print("New FormationStrength (drill_mixed):")
    for e in data["FormationStrength"]:
        print(f"   MD={e['MD']}, UCS={e['UCS']/1e6:.0f} MPa")

    sess.create_configuration(NEW_NAME, data)
    ok = any(c.get("Name") == NEW_NAME for c in sess.configurations())
    print(f"Created '{NEW_NAME}'. Verify on server: {'OK' if ok else 'NOT FOUND'}")


if __name__ == "__main__":
    main()
