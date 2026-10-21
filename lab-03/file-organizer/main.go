package main

import (
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

var categories = map[string]string{
	".pdf": "Documents", ".doc": "Documents",
	".docx": "Documents", ".txt": "Documents",
	".xls": "Documents", ".xlsx": "Documents",
	".ppt": "Documents", ".pptx": "Documents",
	".jpg": "Images", ".jpeg": "Images",
	".png": "Images", ".gif": "Images",
	".webp": "Images", ".svg": "Images",
	".mp4": "Videos", ".mov": "Videos",
	".avi": "Videos", ".mkv": "Videos",
	".webm": "Videos",
	".zip":  "Archives", ".rar": "Archives",
	".7z": "Archives", ".tar": "Archives",
	".gz": "Archives",
}

func categoryFor(filename string) string {
	extension := strings.ToLower(filepath.Ext(filename))
	if category, exists := categories[extension]; exists {
		return category
	}
	return "Other"
}

func listFiles(source string) error {
	entries, err := os.ReadDir(source)
	if err != nil {
		return err
	}

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		info, err := entry.Info()
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() {
			continue
		}

		fmt.Printf("%s -> %s\n", entry.Name(), categoryFor(entry.Name()))
	}
	return nil
}

func organize(source string, dryRun bool) error {
	entries, err := os.ReadDir(source)
	if err != nil {
		return err
	}

	moved := 0

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		info, err := entry.Info()
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() {
			continue
		}

		category := categoryFor(entry.Name())
		destinationDir := filepath.Join(source, category)
		destination := filepath.Join(destinationDir, entry.Name())

		if _, err := os.Lstat(destination); err == nil {
			return fmt.Errorf("файл уже існує: %s", destination)
		} else if !errors.Is(err, os.ErrNotExist) {
			return err
		}

		if dryRun {
			fmt.Printf("[DRY-RUN] %s -> %s\n", entry.Name(), category)
			moved++
			continue
		}

		if err := os.MkdirAll(destinationDir, 0755); err != nil {
			return err
		}

		if err := os.Rename(
			filepath.Join(source, entry.Name()),
			destination,
		); err != nil {
			return err
		}

		fmt.Printf("[OK] %s -> %s\n", entry.Name(), category)
		moved++
	}

	fmt.Printf("Оброблено файлів: %d\n", moved)
	return nil
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "Використання: file-organizer <list|organize> [параметри]")
		os.Exit(2)
	}

	command := os.Args[1]

	flags := flag.NewFlagSet(command, flag.ExitOnError)
	source := flags.String("source", ".", "Папка з файлами")
	dryRun := flags.Bool("dry-run", false, "Показати дії без змін")

	if command != "list" && command != "organize" {
		fmt.Fprintln(os.Stderr, "Невідома команда:", command)
		os.Exit(2)
	}

	if err := flags.Parse(os.Args[2:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}

	info, err := os.Stat(*source)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Помилка:", err)
		os.Exit(1)
	}
	if !info.IsDir() {
		fmt.Fprintln(os.Stderr, "Помилка: source повинен бути папкою")
		os.Exit(1)
	}

	switch command {
	case "list":
		err = listFiles(*source)
	case "organize":
		err = organize(*source, *dryRun)
	}

	if err != nil {
		fmt.Fprintln(os.Stderr, "Помилка:", err)
		os.Exit(1)
	}
}
