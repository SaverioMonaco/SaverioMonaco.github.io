.PHONY: all install generate new app clean

CC = lualatex
DATA_DIR = data
CVB = python3 -m cv_builder
BUILD_DIR = build
CV_SRCS = $(shell find $(BUILD_DIR)/cv -name '*.tex' 2>/dev/null)
DATA_SRCS = $(shell find $(DATA_DIR) -name '*.yaml' 2>/dev/null)

# Build the site: regenerates index.html, gym.html, thesis.html and cv.pdf at the repo root.
all: index.html gym.html thesis.html cv.pdf

install:
	pip install -e .

generate: $(DATA_SRCS)
	$(CVB) build --data-dir $(DATA_DIR) --output-dir $(BUILD_DIR)

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

# Tailored CV + motivation letter for one application, in applications/$(NAME):
#   make new NAME=lanl   -> creates application.yaml and letter.tex to edit
#   make app NAME=lanl   -> builds applications/lanl/cv.pdf and letter.pdf
new:
	@test -n "$(NAME)" || (echo "Usage: make new NAME=<application>" && exit 1)
	$(CVB) new "$(NAME)"

app:
	@test -n "$(NAME)" || (echo "Usage: make app NAME=<application>" && exit 1)
	$(CVB) app "$(NAME)" --data-dir $(DATA_DIR)

clean:
	rm -rf $(BUILD_DIR) index.html gym.html thesis.html cv.pdf
