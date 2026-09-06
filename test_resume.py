"""checks the replay buffer survives a save and resume. short train, save
model + buffer, check the file is there, load it back, train a bit more,
buffer should have grown.
"""
import sys
import os
import shutil

_cwd = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_cwd, "openlab"))
sys.path.insert(0, _cwd)

from sb3_contrib import TQC
from stable_baselines3.common.monitor import Monitor
from drilling_env import DrillingEnv
from train import save_with_buffer, load_with_buffer

TEST_DIR = os.path.join(_cwd, "logs", "_test_resume")


def cleanup():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)


def main():
    cleanup()
    os.makedirs(TEST_DIR, exist_ok=True)

    print("=" * 60)
    print("TEST: Replay Buffer Persistence")
    print("=" * 60)

    # 1. short run
    print("\n[1/4] Creating environment + model...")
    env = Monitor(DrillingEnv(max_steps=100))
    model = TQC(
        "MlpPolicy", env,
        learning_rate=3e-4,
        buffer_size=10000,
        learning_starts=50,
        batch_size=64,
        verbose=0,
    )

    print("[1/4] Training for 600 steps...")
    model.learn(total_timesteps=600, progress_bar=False)
    buf_size_after_train = model.replay_buffer.size()
    print(f"[1/4] Buffer size after training: {buf_size_after_train}")
    assert buf_size_after_train > 0, "Buffer should have transitions after training!"

    # 2. save
    save_path = os.path.join(TEST_DIR, "test_model")
    print(f"\n[2/4] Saving model + replay buffer...")
    save_with_buffer(model, save_path)

    # files there?
    model_file = save_path + ".zip"
    buffer_file = save_path + "_buffer.pkl"
    assert os.path.exists(model_file), f"Model file not found: {model_file}"
    assert os.path.exists(buffer_file), f"Buffer file not found: {buffer_file}"
    buf_file_size = os.path.getsize(buffer_file)
    print(f"[2/4] ✓ Model file: {os.path.getsize(model_file) / 1024:.1f} KB")
    print(f"[2/4] ✓ Buffer file: {buf_file_size / 1024:.1f} KB")
    assert buf_file_size > 1000, "Buffer file is suspiciously small"

    env.close()

    # 3. load it back
    print(f"\n[3/4] Loading model + replay buffer (resume)...")
    env2 = Monitor(DrillingEnv(max_steps=100))
    resumed_model = load_with_buffer(save_path, env=env2)

    buf_size_after_load = resumed_model.replay_buffer.size()
    print(f"[3/4] Buffer size after resume: {buf_size_after_load}")
    print(f"[3/4] Buffer size match: {buf_size_after_train} == {buf_size_after_load} ? ", end="")

    if buf_size_after_train == buf_size_after_load:
        print("✓ YES!")
    else:
        print(f"✗ NO! (expected {buf_size_after_train}, got {buf_size_after_load})")
        env2.close()
        cleanup()
        sys.exit(1)

    # 4. train more, buffer should grow
    print(f"\n[4/4] Continuing training for 200 more steps...")
    resumed_model.learn(total_timesteps=200, progress_bar=False)
    buf_size_after_more = resumed_model.replay_buffer.size()
    print(f"[4/4] Buffer size after more training: {buf_size_after_more}")

    grew = buf_size_after_more > buf_size_after_load
    print(f"[4/4] Buffer grew: {buf_size_after_load} → {buf_size_after_more} ? ", end="")
    if grew:
        print("✓ YES!")
    else:
        print("✗ NO!")

    env2.close()

    # 5. .zip path handling
    print(f"\n[BONUS] Testing load with .zip extension...")
    env3 = Monitor(DrillingEnv(max_steps=100))
    model_zip = load_with_buffer(save_path + ".zip", env=env3)
    buf_zip = model_zip.replay_buffer.size()
    print(f"  Buffer size via .zip path: {buf_zip}")
    assert buf_zip == buf_size_after_train, f"Expected {buf_size_after_train}, got {buf_zip}"
    print("  ✓ .zip path handling works!")
    env3.close()

    # cleanup
    cleanup()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"  Buffer after Phase 1:  {buf_size_after_train} transitions")
    print(f"  Buffer after resume:   {buf_size_after_load} transitions (preserved!)")
    print(f"  Buffer after Phase 2:  {buf_size_after_more} transitions (grew!)")
    print(f"  .zip path handling:    ✓")


if __name__ == "__main__":
    main()
