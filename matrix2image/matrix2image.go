package matrix2image

//assuming that width = height, please don't pass rectangle like matrix (at least fill them to square using zeros)

import (
	"fmt"
	"image"
	"image/draw"
	"image/png"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

const ASSET_PATH = "matrix2image/assets/"

func init() {
	Cache_all()
}

func Visualize(matrix [][]uint8) (*image.RGBA, error) {
	n := len(matrix[0])
	matImage := image.NewRGBA(image.Rect(0, 0, 100*n, 100*n))

	for i := 0; i < n; i++ {
		for j := 0; j < n; j++ {
			valStr := strconv.Itoa(int(matrix[i][j]))
			img, exist := Cached_images[valStr]
			if !exist {
				return matImage, fmt.Errorf("Can't fing field object %v", valStr)
			}
			dp := image.Pt(j*100, i*100)
			rect := image.Rectangle{Min: dp, Max: dp.Add(image.Pt(100, 100))}
			draw.Draw(matImage, rect, img, image.Point{}, draw.Over)

		}
	}
	return matImage, nil
}

func get_file_path() (string, error) {
	wd, err := os.Getwd()
	if err != nil {
		return "", fmt.Errorf("не удалось получить рабочий каталог: %w", err)
	}
	return filepath.Join(wd, ASSET_PATH), nil
}

var Cached_images = make(map[string]image.Image)

func Cache_all() error {
	fp, err := get_file_path()
	if err != nil {
		return fmt.Errorf("Failed to get filepath while caching images %w", err)
	}
	filenames, err := os.ReadDir(fp)
	if err != nil {
		return fmt.Errorf("Failed while reading images to cache %w", err)
	}

	for _, fname := range filenames {
		full_path := filepath.Join(fp, fname.Name())
		numeric := strings.TrimSuffix(fname.Name(), filepath.Ext(fname.Name()))
		file, err := os.Open(full_path)
		if err != nil {
			return fmt.Errorf("Error while asset parsing %w", err)
		}

		Cached_images[numeric], err = png.Decode(file)
		file.Close()
		if err != nil {
			return fmt.Errorf("Error while image caching %w", err)
		}
	}

	return nil
}
