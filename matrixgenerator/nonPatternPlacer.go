package matrixgenerator

import (
	"FE2027/matrixfactory"
	"errors"
	"math"
	"math/rand/v2"
)

//Ставит не паттерновые элементы игрового поля - трубы, холдеры
//Пытается немного оптимизировть через работу с сектором и ранний выход

// findIsolatedSector обходит граф поля в ширину (BFS) от startCell
// и возвращает список индексов всех клеток, достижимых из неё.
// Используется для выделения связного сектора поля.
func findIsolatedSector(mat matrixfactory.FieldMatrix, startCell int) []int {
	queue := make([]int, 0)
	queue = append(queue, 0)

	graphMap, _ := mat.ToGraph()
	sectorCells := make(map[int]struct{})
	sectorCells[startCell] = struct{}{}
	queue[0] = startCell

	for l := 0; l < len(queue); {
		currCell := graphMap[uint16(queue[0])]
		for _, edge := range currCell {
			_, ok := sectorCells[int(edge.ToIDX)]
			if !ok {
				sectorCells[int(edge.ToIDX)] = struct{}{}
				queue = append(queue, int(edge.ToIDX))
			}
		}
		queue = queue[1:]
	}
	finalCells := make([]int, 0)
	for key, _ := range sectorCells {
		finalCells = append(finalCells, key)
	}
	return finalCells
}

// findBiggestSector разбивает всё поле на связные секторы и возвращает
// самый крупный из них (по количеству клеток).
func findBiggestSector(mat matrixfactory.FieldMatrix) []int {
	sMap := make(map[int]struct{})
	// fmt.Printf("Solving: %v", mat.RawData())
	biggestSector := make([]int, 0)
	for {
		next, ok := findNextUndistributedCell(sMap, mat)
		if !ok {
			return biggestSector
		}
		sector := findIsolatedSector(mat, next)
		if len(sector) > len(biggestSector) {
			biggestSector = sector
		}
		for _, val := range sector {
			sMap[val] = struct{}{}
		}
	}
}

// findNextUndistributedCell возвращает индекс первой клетки поля,
// ещё не помеченной как распределённая в sMap. Второе значение — false,
// если таких клеток не осталось.
func findNextUndistributedCell(sMap map[int]struct{}, mat matrixfactory.FieldMatrix) (int, bool) {
	//assuming that matrix is a square!!11!!1
	d := len(mat.RawData()) // min tile - 0, max - d^2 - 1
	for idx := 0; idx < d*d; idx++ {
		_, ok := sMap[idx]
		if !ok {
			return idx, true
		}
	}
	return 0, false
}

// placeHoldersSolvable ищет в самом большом секторе поля все подходящие
// краевые клетки и возвращает список троек подряд идущих клеток
// (горизонтальных и вертикальных), куда можно поставить держатели труб.
func placeHoldersSolvable(fm matrixfactory.FieldMatrix) [][]int {
	sector := findBiggestSector(fm)
	suitableCells := findSuitableEdgeCells(fm, sector)
	suitableMap := make(map[int]struct{})
	for _, cell := range suitableCells {
		suitableMap[cell] = struct{}{}
	}

	size := len(fm.RawData())
	var result [][]int

	// Вспомогательная функция для проверки тройки ячеек
	checkAndAddTriplet := func(c1, c2, c3 int) {
		_, ok1 := suitableMap[c1]
		_, ok2 := suitableMap[c2]
		_, ok3 := suitableMap[c3]

		// Если все три ячейки подходят, сохраняем их как одну тройку
		if ok1 && ok2 && ok3 {
			result = append(result, []int{c1, c2, c3})
		}
	}

	// 1. Поиск горизонтальных троек (слева направо)
	for y := 0; y < size; y++ {
		for x := 0; x < size-2; x++ {
			c1 := y*size + x
			c2 := y*size + (x + 1)
			c3 := y*size + (x + 2)
			checkAndAddTriplet(c1, c2, c3)
		}
	}

	// 2. Поиск вертикальных троек (сверху вниз)
	for x := 0; x < size; x++ {
		for y := 0; y < size-2; y++ {
			c1 := y*size + x
			c2 := (y+1)*size + x
			c3 := (y+2)*size + x
			checkAndAddTriplet(c1, c2, c3)
		}
	}

	return result
}

// applyHoldersPlacement для каждой тройки клеток создаёт копию матрицы поля,
// в которой эти три клетки заменяются на соответствующие держатели труб
// (направление определяется findDirectionByTriplet). Возвращает список
// всех получившихся матриц.
func applyHoldersPlacement(fm matrixfactory.FieldMatrix, placements [][]int) [][][]uint8 {
	rawData := fm.RawData() // тип [][]uint8
	size := len(rawData)
	var matrices [][][]uint8

	for _, triplet := range placements {
		// Создаем глубокую копию с правильным типом [][]uint8
		matrixCopy := make([][]uint8, size)
		for i := range rawData {
			matrixCopy[i] = make([]uint8, size)
			copy(matrixCopy[i], rawData[i])
		}

		// Заменяем элементы тройки на число 22
		for _, cellIdx := range triplet {
			y := cellIdx / size
			x := cellIdx % size
			dir := findDirectionByTriplet(triplet, size)
			holderByDir := fm.GetHolderByDir(dir)
			matrixCopy[y][x] = uint8(holderByDir) // 22 отлично укладывается в uint8 (0-255)
		}

		// Добавляем измененную матрицу в итоговый список
		matrices = append(matrices, matrixCopy)
	}

	return matrices
}

// findDirectionByTriplet определяет ориентацию тройки клеток
// (North/South/East/West) по средней клетке triplet[1].
// Предполагается, что данные корректны.
func findDirectionByTriplet(triplet []int, size int) matrixfactory.DirectionType {
	cell2Check := triplet[1]
	if cell2Check%size == 0 {
		return matrixfactory.West
	}
	if cell2Check%size == size-1 {
		return matrixfactory.East
	}
	if cell2Check/size == 0 {
		return matrixfactory.North
	}
	return matrixfactory.South
}

// findSuitableEdgeCells возвращает индексы краевых клеток поля,
// которые входят в указанный сектор и имеют тип 1 (пол).
// Используется для поиска мест под держатели труб.
func findSuitableEdgeCells(fm matrixfactory.FieldMatrix, sector []int) []int {
	sectorMap := make(map[int]struct{})
	for _, cell := range sector {
		sectorMap[cell] = struct{}{}
	}
	resCells := make([]int, 0)
	mat := fm.RawData()
	size := len(mat)
	for y := 0; y < size; y++ {
		for x := 0; x < size; x++ {
			_, ok := sectorMap[y*size+x]
			if ok {
				if y == 0 || y == size-1 || x == 0 || x == size-1 { //edge cells checking
					if mat[y][x] == 1 { //Hard coded values :((((
						resCells = append(resCells, y*size+x)
					}
				}
			}
		}
	}
	return resCells
}

// convert2Uint8 конвертирует матрицу [][]int в [][]uint8,
// поэлементно приводя значения. Возвращает nil для nil-входа.
func convert2Uint8(matrix [][]int) [][]uint8 {
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

// CreateFullPats генерирует набор полных паттернов поля заданного размера:
// чистое поле → расстановка паттернов → поиск сектора → расстановка держателей →
// прокатка труб → постановка робота. Возвращает список готовых матриц.
func CreateFullPats(size int) [][][]uint8 {
	// 1. Создаем чистую матрицу
	mat := make([][]int, 0, size)
	for idx := 0; idx < size; idx++ {
		s := make([]int, 0, size)
		for x := 0; x < size; x++ {
			s = append(s, 1)
		}
		mat = append(mat, s)
	}

	for {
		ok := placeRandomPatterns(&mat)
		if ok {
			break
		}
	}

	// Превращаем в FieldMatrix
	cleanFM, _ := matrixfactory.NewFieldMatrix(convert2Uint8(mat))

	// 2. Находим сектор ОДИН раз, пока матрица чистая
	cleanSector := findBiggestSector(*cleanFM)
	if len(cleanSector) < 2 {
		return nil
	}

	// 3. Генерируем паттерны с холдерами (используя наш чистый сектор)
	holdersPlaces := placeHoldersSolvable(*cleanFM)
	holderedPats := applyHoldersPlacement(*cleanFM, holdersPlaces)

	var finalPats [][][]uint8

	// 4. Для каждого паттерна с холдерами пытаемся накатать трубы
	for _, holderedPat := range holderedPats {
		// Создаем временную матрицу для текущего паттерна
		fm, err := matrixfactory.NewFieldMatrix(holderedPat)
		if err != nil {
			continue
		}

		// Запускаем плейсер труб с трай 500 и тем самым чистым сектором
		successfulPat, err := rollTubes(*fm, 500, cleanSector, 6)

		if err == nil {
			successfulPat := placeRobot(cleanSector, successfulPat, size)
			finalPats = append(finalPats, successfulPat)
		}
	}

	return finalPats
}

// rollTubes пытается до tryN раз случайно разместить две трубы (21)
// и одну потолочную трубу (22) в клетках сектора так, чтобы все три
// остались в одном секторе и расстояние между двумя трубами было >= delta.
// При успехе возвращает копию матрицы с расстановкой, иначе — ошибку.
func rollTubes(fm matrixfactory.FieldMatrix, tryN int, sector []int, delta float64) ([][]uint8, error) {
	if len(sector) == 0 {
		return nil, errors.New("empty sector")
	}

	rawData := fm.RawData()
	size := len(rawData)
	startCell := sector[0] // Берем первую координату из сектора

	for i := 0; i < tryN; i++ {
		var candidates []int
		var candidatesCeils []int
		for _, cell := range sector {
			y := cell / size
			x := cell % size
			if rawData[y][x] == 1 {
				candidates = append(candidates, cell)
			} else if rawData[y][x] == 2 {
				candidatesCeils = append(candidatesCeils, cell)
			}
		}

		if len(candidates) < 2 {
			continue
		}

		if len(candidatesCeils) == 0 {
			continue
		}

		// rand.N из v2 автоматически генерирует случайные числа
		idx1 := rand.N(len(candidates))
		idx2 := rand.N(len(candidates) - 1)
		idx3 := rand.N(len(candidatesCeils))

		if idx2 >= idx1 {
			idx2++
		}

		cell1 := candidates[idx1]
		cell2 := candidates[idx2]
		cell3 := candidatesCeils[idx3]

		y1, x1 := cell1/size, cell1%size
		y2, x2 := cell2/size, cell2%size
		y3, x3 := cell3/size, cell3%size

		rawData[y1][x1] = 21
		rawData[y2][x2] = 21
		rawData[y3][x3] = 22

		newSector := findIsolatedSector(fm, startCell)

		hasCell1 := false
		hasCell2 := false
		hasCell3 := false
		for _, cell := range newSector {
			if cell == cell1 {
				hasCell1 = true
			}
			if cell == cell2 {
				hasCell2 = true
			}
			if cell == cell3 {
				hasCell3 = true
			}
			if hasCell1 && hasCell2 && hasCell3 {
				break
			}
		}

		if hasCell1 && hasCell2 && hasCell3 {
			if calculateDelta(x1, y1, x2, y2) >= delta {
				matrixCopy := make([][]uint8, size)
				for r := range rawData {
					matrixCopy[r] = make([]uint8, size)
					copy(matrixCopy[r], rawData[r])
				}
				return matrixCopy, nil
			}
		}

		// Роллбэк
		rawData[y1][x1] = 1
		rawData[y2][x2] = 1
		rawData[y3][x3] = 2
	}

	return nil, errors.New("failed to place tubes after maximum tries")
}

// calculateDelta возвращает евклидово расстояние между точками (x1, y1) и (x2, y2).
func calculateDelta(x1 int, y1 int, x2 int, y2 int) float64 {
	return math.Sqrt(float64((x1-x2)*(x1-x2) + (y1-y2)*(y1-y2)))
}

// placeRobot случайно выбирает клетку из сектора и ставит туда робота:
// на пол (1 → 11) или на потолок (2 → 12). Возвращает изменённую матрицу.
func placeRobot(sector []int, pattern [][]uint8, size int) [][]uint8 {
	for {
		p := rand.N(len(sector))
		p = sector[p]
		y, x := p/size, p%size
		if pattern[y][x] == 1 {
			pattern[y][x] = 11
			return pattern
		}
		if pattern[y][x] == 2 {
			pattern[y][x] = 12
			return pattern
		}
	}
}
