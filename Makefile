.PHONY: all install generate clean

CC = lualatex
DATA_DIR = data
BUILD_DIR = build
CV_SRCS = $(shell find $(BUILD_DIR)/cv -name '*.tex' 2>/dev/null)
DATA_SRCS = $(shell find $(DATA_DIR) -name '*.yaml' 2>/dev/null)

# Build the site: regenerates index.html, gym.html, thesis.html and cv.pdf at the repo root.
all: index.html gym.html thesis.html cv.pdf

install:
	pip install -e .

generate: $(DATA_SRCS)
	cv-builder build --data-dir $(DATA_DIR) --output-dir $(BUILD_DIR)

index.html: generate
	cp $(BUILD_DIR)/cv.html $@

gym.html: generate
	cp $(BUILD_DIR)/gym.html $@

thesis.html: generate
	cp $(BUILD_DIR)/thesis.html $@

cv.pdf: generate $(CV_SRCS)
	$(CC) -output-directory=$(BUILD_DIR) $(BUILD_DIR)/cv.tex
	biber $(BUILD_DIR)/cv
	$(CC) -output-directory=$(BUILD_DIR) $(BUILD_DIR)/cv.tex
	$(CC) -output-directory=$(BUILD_DIR) $(BUILD_DIR)/cv.tex
	cp $(BUILD_DIR)/cv.pdf $@

clean:
	rm -rf $(BUILD_DIR) index.html gym.html thesis.html cv.pdf
