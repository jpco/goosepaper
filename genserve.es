#!/usr/local/bin/es

# run before 8:15 am in the goosepaper directory.
# uses `at` (the standard unix utility) and `dir2opds` (most likely installed
# via `go install`).

at 0815 today << 'EOF'
	uv run goosepaper -c config.json -o "gg/$(date -I).epub"
EOF

dir2opds -dir ./gg -port 8080
