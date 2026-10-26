# Seed/cleanup helper for iteration-9 UI tests: python seed_iter9_ui.py seed|clean
import sys
import test_iter9_import_dashboard as t

if __name__ == "__main__":
    t.cleanup()
    if sys.argv[1] == "seed":
        gen = t.seed.__wrapped__(t.login("admin", "admin123")) if hasattr(t.seed, "__wrapped__") else None
        if gen is None:
            raise SystemExit("cannot seed")
        next(gen)
        print("seeded")
    else:
        print("cleaned", t.mongo.items.count_documents({}))
