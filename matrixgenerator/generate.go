package matrixgenerator

import (
	"FE2027/matrixfactory"
	"image"
	"math/rand/v2"
)

var Patterns [][]uint8

func cachePatterns() {
	//НЕЕЕТ ТОЛЬКО НЕ ЭТИ ЦИФРЫ ОПЯТЬ НЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕЕТ
	//(это реально всадники кодового апокалипсиса)
	Patterns = [][]uint8{
		{2}, {2}, {2},
		{2, 2}, {5, 6},
		{5, 2, 2}, {5, 2, 2}, {5, 2, 2, 2}, {5, 2, 2, 2},
		{5, 2, 2, 6}, {5, 2, 2, 2, 6},
	}
}

// PlaceRandomPatterns перебирает все доступные паттерны в случайном порядке
// и пытается гарантированно вставить их в матрицу.
func placeRandomPatterns(mat *[][]int) bool {
	pLen := len(Patterns)
	if pLen == 0 || mat == nil || *mat == nil || len(*mat) == 0 {
		return false
	}

	// Создаем копию индексов паттернов, чтобы перемешать их и обрабатывать случайно
	patIndices := make([]int, pLen)
	for i := 0; i < pLen; i++ {
		patIndices[i] = i
	}

	rand.Shuffle(len(patIndices), func(i, j int) {
		patIndices[i], patIndices[j] = patIndices[j], patIndices[i]
	})

	// Пытаемся разместить каждый паттерн «во что бы то ни стало»
	for _, idx := range patIndices {
		// currPat := Patterns[idx]
		suc := try2InsertAtAllCost(mat, idx)
		if !suc {
			for r := range *mat {
				for c := range (*mat)[r] {
					(*mat)[r][c] = 1
				}
			}
			return false
		}
	}
	return true
}

// try2InsertAtAllCost перебирает всевозможные клетки и повороты,
// автоматически выбирая правильную ориентацию (горизонтально для East/West, вертикально для North/South).
func try2InsertAtAllCost(mat *[][]int, patIDX int) bool {
	allowedIdx := []int{1}

	// 1. Собираем все доступные ячейки на карте
	encodedCells := getPossibleCellsToInsert(*mat, allowedIdx)
	if len(encodedCells) == 0 {
		return false
	}

	// Перемешиваем стартовые ячейки
	rand.Shuffle(len(encodedCells), func(i, j int) {
		encodedCells[i], encodedCells[j] = encodedCells[j], encodedCells[i]
	})

	// 2. Перебор комбинаций: ячейка -> случайный поворот
	for _, encodedPos := range encodedCells {
		// Декодируем координаты на основе логики GetPossibleCellsToInsert
		mLen := len(*mat)
		if mLen == 0 {
			return false
		}
		startY := encodedPos / mLen
		startX := encodedPos % mLen

		// Честная точка для нормальных функций
		startPoint := image.Point{X: startX, Y: startY}

		// Специальная ИНВЕРТИРОВАННАЯ точка для старой функции CheckIsertAbility
		invertedStartPoint := image.Point{X: startY, Y: startX}

		// Создаем локальный слайс направлений для перемешивания
		dirs := []matrixfactory.DirectionType{matrixfactory.North, matrixfactory.South, matrixfactory.East, matrixfactory.West}
		rand.Shuffle(len(dirs), func(i, j int) {
			dirs[i], dirs[j] = dirs[j], dirs[i]
		})

		// Перебираем СЛУЧАЙНЫЕ направления вращения паттерна
		for _, dir := range dirs {
			// ВАЖНО: жестко связываем направление и ориентацию вставки
			var horizontal bool
			if dir == matrixfactory.East || dir == matrixfactory.West {
				horizontal = true
			} else {
				horizontal = false
			}

			rotatedPat := rotatePattern(dir, patIDX)
			intSlice := convertToCopyInt(rotatedPat)

			// 3. Проверка границ и возможности затереть только разрешенные индексы
			if isValidBounds(*mat, len(intSlice), startPoint, horizontal) {

				// Передаем invertedStartPoint, чтобы обойти баг внутри CheckIsertAbility
				if checkIsertAbility(mat, &intSlice, invertedStartPoint, horizontal, allowedIdx) {

					// Используем нормальный startPoint для финальной вставки в матрицу
					insertSliceInto(mat, &intSlice, startPoint, horizontal)
					return true
				}
			}
		}
	}

	return false
}
