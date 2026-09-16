package main

import (
	"FE2027/generatorHandler"
	"FE2027/matrix2image"
	"FE2027/matrixgenerator"
	"fmt"
	"image"
	"image/png"
	"math/rand/v2"
	"os"
)

// Вспомогательная функция в main для записи любого image.Image в файл
func saveToFile(filename string, img image.Image) error {
	file, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer file.Close()
	return png.Encode(file, img)
}

func GenerateWeightedNumber() int {
	// Генерируем случайное число от 0 до 63 включительно (всего 64 исхода)
	n := rand.IntN(64)

	switch {
	case n < 45:
		// Первые 45 исходов (от 0 до 44) дают единицу
		return 1
	case n < 55:
		// Следующие 10 исходов (от 45 до 54) дают двойку
		return 2
	default:
		// Оставшиеся 9 исходов (от 55 до 63) равномерно распределяем между 3, 4, 5 и 6.
		// Формула rand.IntN(4) + 3 вернет случайное число из диапазона [3, 4, 5, 6]
		return rand.IntN(4) + 3
	}
}

// Convert2Uint8 конвертирует матрицу [][]int в [][]uint8
func Convert2Uint8(matrix [][]int) [][]uint8 {
	if matrix == nil {
		return nil
	}

	// Создаем внешнюю матрицу нужной длины
	result := make([][]uint8, len(matrix))

	for i, row := range matrix {
		// Создаем внутренний срез для текущей строки
		result[i] = make([]uint8, len(row))
		for j, val := range row {
			// Явно приводим каждый int к uint8
			result[i][j] = uint8(val)
		}
	}

	return result
}

func main() {
	// 1. Инициализация кэша вашего движка картинок и паттернов
	err := matrix2image.Cache_all()
	if err != nil {
		fmt.Printf("Ошибка кэширования картинок: %v\n", err)
		return
	}

	matrixgenerator.CacheDiredPatterns()

	fmt.Println("Запуск пайплайна генерации...")

	// pats := generatorHandler.GenerateFullyLegitPatterns(8, 1)
	// // var c int
	// fmt.Print(len(pats))
	// for n, pat := range pats {
	// 	// c += 1
	// 	// fmt.Printf("%v\n", c)
	// 	name := fmt.Sprintf("legit_%v.png", n)
	// 	f, _ := matrix2image.Visualize(pat)
	// 	fm, _ := matrixfactory.NewFieldMatrix(pat)
	// 	pf, _ := pathfind.NewMatrixGraph(fm)
	// 	routes, _ := patsolve.Solve(fm, &pf)
	// 	matrix2image.DrawRoutes(routes, f)
	// 	saveToFile(name, f)
	// }

	generatorHandler.GenerateFullyLegitPatterns(8, 10_000)

	// for x := 0; x < 1000; x++ {
	// 	matrixgenerator.CreateFullPats(8)
	// 	if x%25 == 0 {
	// 		fmt.Printf("%v\n", x)
	// 	}
	// }

}
