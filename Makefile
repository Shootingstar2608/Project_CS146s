.PHONY: dev stop dev-backend dev-frontend test seed lint clean

# ── One-click run toàn bộ hệ thống ──
dev:
	docker compose up --build

# Dừng toàn bộ
stop:
	docker compose down

# ── Dev riêng từng service (không cần Docker) ──
dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

# ── Testing ──
test:
	cd backend && python -m pytest tests/ -v

# ── Chạy pipeline trích xuất cho sample papers ──
seed:
	cd pipeline && python run_pipeline.py --input ../data/sample_papers/

# ── Code quality ──
lint:
	cd backend && ruff check . --fix
	cd pipeline && ruff check . --fix
	cd agent && ruff check . --fix

# ── Dọn dẹp ──
clean:
	docker compose down -v --rmi local
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
