package generatorHandler

import (
	"FE2027/matrix2image"
	"FE2027/matrixfactory"
	"FE2027/matrixgenerator"
	"FE2027/pathfind"
	"FE2027/patsolve"
	"image"
	"image/png"
	"os"
)

// Returns a 2d slices with 100% legit patterns which follows all category rules
// At least it is supposed to
func GenerateFullyLegitPatterns(size int, number int) [][][]uint8 {
	patterns := make([][][]uint8, 0, number)
	matrixgenerator.CacheDiredPatterns()
	for {
		pats := matrixgenerator.CreateFullPats(size)
		for _, pat := range pats {
			fm, _ := matrixfactory.NewFieldMatrix(pat)
			pf, _ := pathfind.NewMatrixGraph(fm)
			img, _ := matrix2image.Visualize(pat)
			saveToFile("preSolved.png", img)
			routes, err := patsolve.Solve(fm, &pf)
			if err == nil {
				restoreTubesByRoute(pat, routes, size)
				patterns = append(patterns, pat)
				if len(patterns) == number {
					return patterns
				}
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

func saveToFile(filename string, img image.Image) error {
	file, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer file.Close()
	return png.Encode(file, img)
}
