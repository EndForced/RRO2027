package patsolve

import (
	"fmt"
	"math"

	prmt "github.com/gitchander/permutation"
)

// да это солвер. Он очень мало знает о поведении клеток.
type FMatrix interface {
	RawData() [][]uint8
	TubeIDXGetter() []int
	HolderIDXGetter() []int
	CalculateRouteLenght([]int) int
	RobotIDXGetter() []int
}

type PFinder interface {
	PathFind(FromIDX int, ToIDX int) ([]int, error)
	CutCellsNeighboursExceptOne(targetCell int, allowedCell int) //метод для предотвращения багов с сквозным прохожденеим трубы. Делает так, что на дальнейшем маршруте
	//из клетки можно будет выехать только так, как в нее попали
	//Это  может создать странное поведение, но если вызвать рестор целл коннекшнс - все вернется обратно
	RestoreCellConnections()
}

// findIDS ищет в матрице все клетки, чьи ID входят в переданный список id,
// и возвращает их линейные индексы (y*size + x).
// Используется для поиска позиций труб, держателей и робота.
func findIDS(mat [][]uint8, id []int) []int {
	s := len(mat)
	idm := make(map[int]struct{})
	for _, idX := range id {
		idm[idX] = struct{}{}
	}
	var resIdx []int

	for y := 0; y < s; y++ {
		for x := 0; x < s; x++ {
			cell := mat[y][x]
			_, exist := idm[int(cell)]
			if exist {
				resIdx = append(resIdx, y*s+x)
			}
		}
	}
	// fmt.Printf("Finding: %v in mat %v, found: %v", id, mat, resIdx)
	return resIdx
}

// Solve — главная точка входа солвера.
// Перебирает все перестановки труб и держателей, для каждой строит маршрут
// робот → трубы → держатели через routeHandler и выбирает вариант с минимальным весом.
// Возвращает лучший набор сегментов маршрута или ошибку, если поле пустое,
// роботов не ровно один или ни один вариант не оказался валидным.
func Solve(mat FMatrix, pf PFinder) ([][]int, error) {
	rawCells := mat.RawData()
	if len(rawCells) == 0 {
		return nil, fmt.Errorf("Can't solve empty matrix\nYou probably should check NewFieldMatrix method errors")
	}

	tubesIDX := findIDS(rawCells, mat.TubeIDXGetter())
	holdersIDX := findIDS(rawCells, mat.HolderIDXGetter())
	robotIDX := findIDS(rawCells, mat.RobotIDXGetter())

	if len(robotIDX) > 1 || len(robotIDX) == 0 {
		return nil, fmt.Errorf("Can't solve pattern with %v robots", len(robotIDX))
	}

	minWeight := math.MaxInt
	var bestSegments [][]int

	tubesPerm := prmt.NewSlicePermutator(tubesIDX)

	for okTubes := true; okTubes; okTubes = tubesPerm.NextPermutation() {
		holdersClone := make([]int, len(holdersIDX))
		copy(holdersClone, holdersIDX)
		holdersPerm := prmt.NewSlicePermutator(holdersClone)

		for okHolders := true; okHolders; okHolders = holdersPerm.NextPermutation() {

			totalPointsLen := len(robotIDX) + len(tubesIDX) + len(holdersIDX)
			currentQueryRoute := make([]int, 0, totalPointsLen)

			currentQueryRoute = append(currentQueryRoute, robotIDX...)
			currentQueryRoute = append(currentQueryRoute, tubesIDX...)
			currentQueryRoute = append(currentQueryRoute, holdersIDX...)

			segments, weight, success := routeHandler(currentQueryRoute, mat, pf)
			pf.RestoreCellConnections() // небольшой костыль

			if success && weight < minWeight {
				minWeight = weight
				bestSegments = segments
			}
		}
	}

	if bestSegments == nil {
		return nil, fmt.Errorf("can't find any valid route for holders and tubes")
	}
	return bestSegments, nil
}

// routeHandler строит маршрут по последовательности точек route,
// соединяя их попарно через pf.PathFind. Для каждого найденного сегмента
// вызывает CutCellsNeighboursExceptOne, чтобы запретить сквозной проезд
// через последнюю клетку сегмента. Возвращает список сегментов, суммарный вес
// и признак успеха. Если хотя бы один сегмент не найден или вырожден (длина < 2),
// возвращает success = false.
func routeHandler(route []int, mat FMatrix, pf PFinder) ([][]int, int, bool) {
	weigth := 0
	routes := make([][]int, 0, len(route)-1)

	for pointIndex := range len(route) - 1 {
		routeSingle, err := pf.PathFind(route[pointIndex], route[pointIndex+1])
		if err != nil {
			// fmt.Printf("Error in routeHandler %v", err)
			return make([][]int, 0), 0, false
		}
		routeL := len(routeSingle) - 1
		if len(routeSingle) == 1 { //маршрут должен иметь как минимум 2 клетки - старт и финиш
			return make([][]int, 0), 0, false
		}
		pf.CutCellsNeighboursExceptOne(routeSingle[routeL], routeSingle[routeL-1])
		routes = append(routes, routeSingle)
		weigth += mat.CalculateRouteLenght(routeSingle)
	}

	return routes, weigth, true
}
