dev:
	uv run copier copy . .dev/acme --vcs-ref HEAD --defaults --overwrite --trust \
	  -d product_name="Acme Reports" -d product_slug=acme-reports
