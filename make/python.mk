.PHONY: lint
lint: ## Run Linter
	uv run ruff check .
	uv run mypy .

.PHONY: fmt
fmt: ## Run formatter
	uv run ruff check --fix .
	uv run ruff format .

.PHONY: test
test: ## Run tests
	uv run pytest .

.PHONY: lock
lock: ## Lock dependencies
	uv lock

.PHONY: install
install: ## Setup the project
	uv sync --all-groups
