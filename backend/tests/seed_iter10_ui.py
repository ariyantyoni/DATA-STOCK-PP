# Seed / cleanup helper for iteration 10 dashboard UI testing (python seed_iter10_ui.py seed|clean)
import sys
import test_iter10_dashboard_kpi as t

if __name__ == "__main__":
    if sys.argv[1] == "seed":
        g = t.seed.__wrapped__(t.login("admin", "admin123"))
        next(g)
        print("seeded", t.STOCK_IDS)
    else:
        t.cleanup()
        print("cleaned")
