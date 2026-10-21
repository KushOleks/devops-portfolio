package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestCategoryFor(t *testing.T) {
	tests := []struct {
		filename string
		expected string
	}{
		{"report.pdf", "Documents"},
		{"notes.txt", "Documents"},
		{"photo.jpg", "Images"},
		{"PHOTO.PNG", "Images"},
		{"video.mp4", "Videos"},
		{"archive.zip", "Archives"},
		{"unknown.xyz", "Other"},
	}

	for _, test := range tests {
		t.Run(test.filename, func(t *testing.T) {
			actual := categoryFor(test.filename)

			if actual != test.expected {
				t.Errorf(
					"categoryFor(%q) = %q, очікувалося %q",
					test.filename,
					actual,
					test.expected,
				)
			}
		})
	}
}

func TestListFiles(t *testing.T) {
	dir := t.TempDir()

	err := os.WriteFile(
		filepath.Join(dir, "report.pdf"),
		[]byte("test"),
		0644,
	)
	if err != nil {
		t.Fatal(err)
	}

	if err := listFiles(dir); err != nil {
		t.Fatalf("Помилка listFiles: %v", err)
	}

	if _, err := os.Stat(filepath.Join(dir, "report.pdf")); err != nil {
		t.Fatal("Команда list не повинна переміщувати файли")
	}
}

func TestOrganizeDryRun(t *testing.T) {
	dir := t.TempDir()
	source := filepath.Join(dir, "photo.jpg")

	if err := os.WriteFile(source, []byte("image"), 0644); err != nil {
		t.Fatal(err)
	}

	if err := organize(dir, true); err != nil {
		t.Fatalf("Помилка dry-run: %v", err)
	}

	if _, err := os.Stat(source); err != nil {
		t.Fatal("Dry-run не повинен переміщувати файл")
	}

	if _, err := os.Stat(filepath.Join(dir, "Images")); !os.IsNotExist(err) {
		t.Fatal("Dry-run не повинен створювати папки")
	}
}

func TestOrganizeFiles(t *testing.T) {
	dir := t.TempDir()

	files := map[string]string{
		"report.pdf": "Documents",
		"photo.jpg":  "Images",
		"video.mp4":  "Videos",
		"backup.zip": "Archives",
		"file.xyz":   "Other",
	}

	for filename := range files {
		if err := os.WriteFile(
			filepath.Join(dir, filename),
			[]byte("test"),
			0644,
		); err != nil {
			t.Fatal(err)
		}
	}

	if err := organize(dir, false); err != nil {
		t.Fatalf("Помилка organize: %v", err)
	}

	for filename, category := range files {
		destination := filepath.Join(dir, category, filename)

		if _, err := os.Stat(destination); err != nil {
			t.Errorf("Файл %s не переміщено: %v", filename, err)
		}
	}
}

func TestPreventOverwrite(t *testing.T) {
	dir := t.TempDir()
	destinationDir := filepath.Join(dir, "Documents")

	if err := os.Mkdir(destinationDir, 0755); err != nil {
		t.Fatal(err)
	}

	source := filepath.Join(dir, "report.pdf")
	destination := filepath.Join(destinationDir, "report.pdf")

	if err := os.WriteFile(source, []byte("new"), 0644); err != nil {
		t.Fatal(err)
	}

	if err := os.WriteFile(destination, []byte("old"), 0644); err != nil {
		t.Fatal(err)
	}

	if err := organize(dir, false); err == nil {
		t.Fatal("Очікувалася помилка через існуючий файл")
	}

	content, err := os.ReadFile(destination)
	if err != nil {
		t.Fatal(err)
	}

	if string(content) != "old" {
		t.Fatal("Існуючий файл було перезаписано")
	}
}

func TestOrganizeEmptyDirectory(t *testing.T) {
	dir := t.TempDir()

	if err := organize(dir, false); err != nil {
		t.Fatalf("Порожня папка не повинна спричиняти помилку: %v", err)
	}
}
