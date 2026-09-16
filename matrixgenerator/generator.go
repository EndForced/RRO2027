package matrixgenerator

import (
	"FE2027/matrixfactory"
	"image"
)

var cachedDiredPatterns []map[matrixfactory.DirectionType][]uint8

//Вспомогательные функции для паттерн плейсера
//Реалиовано кэширование всех вариантов поворота всех паттернов - поэтому 2 функции для получения повернутого паттерна

// CacheDiredPatterns один раз строит кэш всех паттернов из Patterns
// во всех четырёх направлениях и сохраняет его в cachedDiredPatterns.
// Должна вызываться до использования rotatePattern.
func CacheDiredPatterns() {
	cachePatterns()
	dType := []matrixfactory.DirectionType{
		matrixfactory.North, matrixfactory.South, matrixfactory.East, matrixfactory.West,
	}
	for _, pat := range Patterns {
		m := make(map[matrixfactory.DirectionType][]uint8)
		for _, dir := range dType {
			m[dir] = rotatePattern2Cache(dir, pat)

		}
		cachedDiredPatterns = append(cachedDiredPatterns, m)
	}
	// fmt.Print(cachedDiredPatterns)
}

// getReplacementMap возвращает карту замены ID клеток при повороте паттерна
// в заданном направлении. Меняются только рампы (5 и 6); пол и потолок
// остаются как есть. Предполагается, что существуют только рампы,
// смотрящие на запад и восток.
// assuming that possible ramps are only west and east facing that means they have id 6 and 5
func getReplacementMap(dir matrixfactory.DirectionType) map[int]int {

	tilesSwapMap := make(map[int]int)
	tilesSwapMap[1] = 1
	tilesSwapMap[2] = 2
	switch dir {
	case matrixfactory.North:
		tilesSwapMap[5] = 4
		tilesSwapMap[6] = 3
	case matrixfactory.South:
		tilesSwapMap[5] = 3
		tilesSwapMap[6] = 4
	case matrixfactory.East:
		tilesSwapMap[5] = 5
		tilesSwapMap[6] = 6
	case matrixfactory.West:
		tilesSwapMap[5] = 6
		tilesSwapMap[6] = 5
	}
	return tilesSwapMap
}

// reverseSlice переворачивает срез на месте (in-place).
func reverseSlice(pat []uint8) {
	for i, j := 0, len(pat)-1; i < j; i, j = i+1, j-1 {
		pat[i], pat[j] = pat[j], pat[i]
	}
}

// applyReplacementMap возвращает новый срез, в котором каждый ID заменён
// согласно swapMap. ID, отсутствующие в карте, остаются без изменений.
func applyReplacementMap(pat []uint8, swapMap map[int]int) []uint8 {
	out := make([]uint8, len(pat))
	for i, id := range pat {
		if newVal, exists := swapMap[int(id)]; exists {
			out[i] = uint8(newVal)
		} else {
			out[i] = id // иначе оставляем как было
		}
	}
	return out
}

// rotatePattern2Cache возвращает новый срез — паттерн, повёрнутый
// в направлении dir. Исходит из того, что исходный паттерн всегда
// вставляется сверху вниз или слева направо (East — базовое направление).
// Поворачивает паттерны из логики что слайсы  всегда вставляются сверху вниз или слева направо
func rotatePattern2Cache(dir matrixfactory.DirectionType, pat []uint8) []uint8 {
	swapMap := getReplacementMap(dir)

	switch dir {
	case matrixfactory.East:
		out := make([]uint8, len(pat))
		copy(out, pat)
		return out

	case matrixfactory.West:
		out := applyReplacementMap(pat, swapMap)
		reverseSlice(out)
		return out

	case matrixfactory.North:
		out := applyReplacementMap(pat, swapMap)
		return out

	case matrixfactory.South:
		out := applyReplacementMap(pat, swapMap)
		reverseSlice(out)
		return out

	default:
		out := make([]uint8, len(pat))
		copy(out, pat)
		return out
	}
}

// rotatePattern возвращает закэшированный повёрнутый паттерн по его индексу
// pIDX и направлению dir. Требует предварительного вызова CacheDiredPatterns.
func rotatePattern(dir matrixfactory.DirectionType, pIDX int) []uint8 {
	return cachedDiredPatterns[pIDX][dir]
}

// isValidBounds проверяет, что срез длины sLen, вставляемый в позицию start,
// не выходит за границы матрицы m. horizontal == true — вставка по строке,
// false — по столбцу.
func isValidBounds(m [][]int, sLen int, start image.Point, horizontal bool) bool {
	if horizontal {
		if start.Y < 0 || start.Y >= len(m) || start.X < 0 || start.X+sLen > len(m[start.Y]) {
			return false
		}
	} else {
		if start.X < 0 || start.Y < 0 || start.Y+sLen > len(m) {
			return false
		}
		// Дополнительная проверка ширины строк при вертикальной вставке
		for i := 0; i < sLen; i++ {
			if start.X >= len(m[start.Y+i]) {
				return false
			}
		}
	}
	return true
}

// insertSliceInto копирует элементы slice в матрицу mat начиная с позиции start
// (по строке или по столбцу). Предполагается, что границы уже проверены.
// Возвращает false при nil-аргументах.
func insertSliceInto(mat *[][]int, slice *[]int, start image.Point, horizontal bool) bool {
	if mat == nil || slice == nil || *mat == nil || *slice == nil {
		return false
	}

	m := *mat
	s := *slice
	sLen := len(s)

	// Вставка элементов (гарантированно в пределах границ)
	if horizontal {
		for i := 0; i < sLen; i++ {
			m[start.Y][start.X+i] = s[i]
		}
	} else {
		for i := 0; i < sLen; i++ {
			m[start.Y+i][start.X] = s[i]
		}
	}

	return true
}

// checkIsertAbility проверяет, можно ли вставить slice в позицию start:
// все клетки под срезом должны входить в allowedIdx. Вставка идёт по строке
// (horizontal == true) или по столбцу. Пустой slice — вставка разрешена;
// пустой allowedIdx — запрещена. Границы не проверяются.
func checkIsertAbility(mat *[][]int, slice *[]int, start image.Point, horizontal bool, allowedIdx []int) bool {
	// Use only if you sure that slice won't get out of mat's range
	//Im trying to understand pointers
	//That's not hard in read only funcs
	if len(*slice) == 0 {
		return true
	}

	if len(allowedIdx) == 0 {
		return false
	}

	m := *mat
	allowedMap := make(map[int]struct{})
	for _, allowed := range allowedIdx {
		allowedMap[allowed] = struct{}{}
	}

	sy, sx := start.X, start.Y
	sliceLen := len(*slice)
	if horizontal {
		for x := sx; x < sx+sliceLen; x++ {
			cell := m[sy][x]
			_, ok := allowedMap[cell]
			if !ok {
				return false
			}
		}
		return true
	}

	if !horizontal {
		for y := sy; y < sy+sliceLen; y++ {
			cell := m[y][sx]
			_, ok := allowedMap[cell]
			if !ok {
				return false
			}
		}
		return true
	}
	return false
}

// getPossibleCellsToInsert возвращает индексы клеток матрицы,
// чьи ID входят в allowedIdx. Используется для поиска позиций,
// куда можно вставить паттерн.
func getPossibleCellsToInsert(mat [][]int, allowedIdx []int) []int {
	allowedMap := make(map[int]struct{})
	res := make([]int, 64)
	mLen := len(mat)

	for _, allowed := range allowedIdx {
		allowedMap[allowed] = struct{}{}
	}

	for y := 0; y < mLen-1; y++ {
		for x := 0; x < mLen-1; x++ {
			cellId := mat[y][x]
			_, ok := allowedMap[cellId]
			if ok {
				res = append(res, y*mLen+x)
			}
		}
	}
	return res
}

// convertToCopyInt конвертирует []uint8 в новый срез []int
// (поэлементное приведение с копированием).
// Вспомогательная функция для конвертации []uint8 в []int
func convertToCopyInt(in []uint8) []int {
	out := make([]int, len(in))
	for i, v := range in {
		out[i] = int(v)
	}
	return out
}
