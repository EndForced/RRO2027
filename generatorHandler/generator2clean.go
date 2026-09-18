package generatorHandler

import (
	"FE2027/matrixfactory"
	"FE2027/matrixgenerator"
	"FE2027/pathfind"
	"FE2027/patsolve"
	"math/rand/v2"
)

type InsertElement struct {
	Pattern [][]uint8
	Route   [][]int
}

// Returns a 2d slices with 100% legit patterns which follows all category rules
// At least it is supposed to
func GenerateFullyLegitPatterns(size int, number int) []InsertElement {
	patterns := make([]InsertElement, 0, number)
	for {
		pats := matrixgenerator.CreateFullPats(size)
		for _, pat := range pats {
			fm, _ := matrixfactory.NewFieldMatrix(pat)
			pf, _ := pathfind.NewMatrixGraph(fm)
			routes, err := patsolve.Solve(fm, &pf)
			if err == nil {
				restoreTubesByRoute(pat, routes, size)
				replaceTubesWithColoredVersion(pat)
				element := InsertElement{
					Pattern: pat,
					Route:   routes,
				}
				patterns = append(patterns, element)
				if len(patterns) == number {
					return patterns
				}
			}
		}
	}
}

func replaceTubesWithColoredVersion(mat [][]uint8) {
	redCount := rand.N(2) + 1
	var tubes []int
	if redCount == 1 {
		tubes = append(tubes, 0, 0, 1)
	}
	if redCount == 2 {
		tubes = append(tubes, 0, 1, 1)
	}

	rand.Shuffle(len(tubes), func(i, j int) {
		tubes[i], tubes[j] = tubes[j], tubes[i]
	})

	mL := len(mat)
	for x := 0; x < mL; x++ {
		for y := 0; y < mL; y++ {
			cell := mat[y][x]
			rep := tubeReplacement(int(cell))
			if len(rep) > 0 {
				mat[y][x] = uint8(rep[tubes[0]])
				tubes = tubes[1:]
			}
		}
	}
}

// Самые жесткие костыли среди всех пакетов, так что я решил вынести в отдельный файл
func restoreTubesByRoute(mat [][]uint8, routes [][]int, size int) [][]uint8 {
	l := len(routes)
	routes = routes[:l-3]

	for _, route := range routes {
		// fmt.Print(route)
		rLen := len(route)
		connectionCells := route[rLen-2:] //получение последней пары клеток чтобы определить направление
		// fmt.Print(connectionCells)
		cellBeforeTube := connectionCells[0]
		y, x := cellBeforeTube/size, cellBeforeTube%size
		// fmt.Printf("x %v y %v\n", x, y)

		var floor int
		if mat[y][x] == 1 || mat[y][x] == 11 {
			floor = 1
		} else {
			floor = 2
		}
		newTube := getTubeByFloorAnd2Cells(floor, connectionCells, size)
		cellWithTube := connectionCells[1]
		y, x = cellWithTube/size, cellWithTube%size
		mat[y][x] = uint8(newTube)
	}
	return mat
}

func getTubeByFloorAnd2Cells(floor int, cells []int, size int) int {
	y1 := cells[0] / size
	y2 := cells[1] / size
	if floor == 2 {
		if y2 != y1 {
			return 9
		}
		return 10
	}
	if y1 != y2 {
		return 7
	}
	return 8

}

func tubeReplacement(idx int) []int {
	switch idx {
	case 7:
		return []int{23, 27}
	case 8:
		return []int{24, 28}
	case 9:
		return []int{25, 29}
	case 10:
		return []int{26, 30}

	}
	return make([]int, 0)
}
