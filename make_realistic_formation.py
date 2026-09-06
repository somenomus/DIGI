"""make the 'drill_realistic' base config on openlab.

the original 'drill' config has a 200 MPa layer NORCE said is too hard to
drill, so this squeezes the formation into 50-70 MPa and keeps the layering
(same MD boundaries, same friction angle). the original config is untouched.

new = 50 + (old - 50) * 20 / 150, so 50 -> 50, 100 -> 57, 150 -> 63, 200 -> 70

with the multipliers: 1x = 50-70 MPa, 0.4x = 20-28, 0.2x = 10-14
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "openlab"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg
import openlab

NEW_NAME = "drill_realistic"

# UCS per layer in Pa, same MD boundaries as the base
NEW_UCS_PA = {
    50_000_000: 50_000_000,
    100_000_000: 57_000_000,
    150_000_000: 63_000_000,
    200_000_000: 70_000_000,
}


def main():
    openlab.login.switch_user(new_user=cfg.OPENLAB_EMAIL, new_key=cfg.OPENLAB_API_KEY,
                              new_licenseguid=cfg.OPENLAB_LICENSE_GUID, environment="prod")
    sess = openlab.http_client(username=cfg.OPENLAB_EMAIL, apikey=cfg.OPENLAB_API_KEY,
                               licenseguid=cfg.OPENLAB_LICENSE_GUID)
    configs = sess.configurations()

    # already there?
    if any(c.get("Name") == NEW_NAME for c in configs):
        print(f"Config '{NEW_NAME}' already exists — skipping creation.")
        return

    base = [c for c in configs if c.get("Name") == cfg.CONFIG_NAME]
    if not base:
        print(f"ERROR: base config '{cfg.CONFIG_NAME}' not found on server.")
        return
    base_id = base[0].get("ConfigurationID") or base[0].get("Id")
    data = sess.configuration_data(base_id)

    print("Original FormationStrength:")
    for e in data.get("FormationStrength", []):
        print("  ", e)

    for fs in data.get("FormationStrength", []):
        old = fs["UCS"]
        fs["UCS"] = NEW_UCS_PA.get(old, max(50_000_000, min(70_000_000, old)))

    print("\nNew FormationStrength (50-70 MPa):")
    for e in data.get("FormationStrength", []):
        print(f"   MD={e['MD']}, UCS={e['UCS']/1e6:.0f} MPa")

    sess.create_configuration(NEW_NAME, data)
    print(f"\nCreated config '{NEW_NAME}'.")

    # check it landed
    configs = sess.configurations()
    ok = any(c.get("Name") == NEW_NAME for c in configs)
    print(f"Verify on server: {'OK' if ok else 'NOT FOUND'}")


if __name__ == "__main__":
    main()
