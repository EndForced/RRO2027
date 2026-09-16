package file_operator

import (
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
)

const SaveFile = "data/pats.bin"
const PatSizeBytes = 48

func get_file_path() (string, error) {
	wd, err := os.Getwd()
	if err != nil {
		return "", fmt.Errorf("не удалось получить рабочий каталог: %w", err)
	}
	return filepath.Join(wd, SaveFile), nil
}

func Init() error {
	fp, err := get_file_path()
	if err != nil {
		return err
	}

	_, err = os.ReadFile(fp)
	if err != nil {
		log.Println("No pat file found. Trying to create a new one")

		errDir := os.MkdirAll(filepath.Dir(fp), 0755)
		if errDir != nil {
			return fmt.Errorf("не удалось создать папку для файла: %w", errDir)
		}

		err = os.WriteFile(fp, []byte{}, 0644)
		if err != nil {
			return fmt.Errorf("не удалось создать файл для расстановок: %w", err)
		}
	}
	log.Println("Successfully initialized")
	return nil
}

func Insert(matrix [8][8]uint) error {
	var serialized []byte
	for i := 0; i < 8; i++ {
		for j := 0; j < 8; j += 4 {
			a := uint8(matrix[i][j])
			b := uint8(matrix[i][j+1])
			c := uint8(matrix[i][j+2])
			d := uint8(matrix[i][j+3])

			n1 := (a << 2) | (b >> 4)
			n2 := (b << 4) | (c >> 2)
			n3 := (c << 6) | d

			serialized = append(serialized, n1, n2, n3)
		}
	}

	fp, err := get_file_path()
	if err != nil {
		return err
	}

	file, err := os.OpenFile(fp, os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Errorf("failed to open file for append: %w", err)
	}
	defer file.Close()

	_, err = file.Write(serialized)
	if err != nil {
		return fmt.Errorf("failed to write data to file: %w", err)
	}

	return nil
}

func GetPatsNumber() (int, error) {
	fp, err := get_file_path()
	if err != nil {
		return 0, err
	}

	file, err := os.Open(fp)
	if err != nil {
		return 0, fmt.Errorf("failed to open pattern file: %w", err)
	}
	defer file.Close()

	stat, err := file.Stat()
	if err != nil {
		return 0, fmt.Errorf("failed to get pattern file size: %w", err)
	}

	if stat.Size()%PatSizeBytes != 0 {
		return 0, fmt.Errorf("pattern file is corrupted (size %d is not a multiple of %d)", stat.Size(), PatSizeBytes)
	}

	return int(stat.Size()) / PatSizeBytes, nil
}

func GetNsPat(n int) ([8][8]int, error) {
	var matrix [8][8]int
	offset := int64(PatSizeBytes * n)

	fp, err := get_file_path()
	if err != nil {
		return matrix, err
	}

	file, err := os.Open(fp)
	if err != nil {
		return matrix, fmt.Errorf("failed to open pattern file: %w", err)
	}
	defer file.Close()

	_, err = file.Seek(offset, io.SeekStart)
	if err != nil {
		return matrix, fmt.Errorf("failed to seek to pattern index %d: %w", n, err)
	}

	buffer := make([]byte, PatSizeBytes)
	_, err = io.ReadFull(file, buffer)
	if err != nil {
		return matrix, fmt.Errorf("failed to read pattern data: %w", err)
	}

	return deserialize([PatSizeBytes]byte(buffer)), nil
}

func deserialize(data [PatSizeBytes]byte) [8][8]int {
	var matrix [8][8]int
	byteIdx := 0

	for i := 0; i < 8; i++ {
		for j := 0; j < 8; j += 4 {
			n1 := data[byteIdx]
			n2 := data[byteIdx+1]
			n3 := data[byteIdx+2]
			byteIdx += 3

			a := n1 >> 2
			b := ((n1 & 0b11) << 4) | (n2 >> 4)
			c := ((n2 & 0b1111) << 2) | (n3 >> 6)
			d := n3 & 0b111111

			matrix[i][j] = int(a)
			matrix[i][j+1] = int(b)
			matrix[i][j+2] = int(c)
			matrix[i][j+3] = int(d)
		}
	}
	return matrix
}
