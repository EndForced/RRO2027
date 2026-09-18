package matrixassembler

import (
	"TgPatBot/file_operator"
	"TgPatBot/matrix2image"
	"fmt"
	"image"
	"math/rand/v2"
)

type TgSupplier struct {
	Pattern       image.Image
	PatternSolved image.Image
	PatternIDX    int
}

func init() {
	matrix2image.Cache_all()
	fmt.Print("Matrix2image assets cached")
}

func GetRandPat() TgSupplier {
	totalPatternCount, err := file_operator.GetPatsNumber()
	if err != nil {
		fmt.Errorf("Can't get pats number: %v\n", err)
	}
	patN := rand.N(totalPatternCount)
	return getNthPat(patN)

}

func getNthPat(patN int) TgSupplier {
	pat, route, err := file_operator.GetNsPat(patN)
	if err != nil {
		fmt.Errorf("Error while getting %v pat %v\n", patN, err)
	}
	img1, err := matrix2image.Visualize(convert2Uint8(pat))
	img2, err := matrix2image.Visualize(convert2Uint8(pat))
	matrix2image.DrawRoutes(route, img2)

	return TgSupplier{
		Pattern:       img1,
		PatternSolved: img2,
		PatternIDX:    patN,
	}
}

func convert2Uint8(mat [][]int) [][]uint8 {
	out := make([][]uint8, 0, 64)
	for y := 0; y < len(mat); y++ {
		out[y] = make([]uint8, len(mat[y]))
		for x := 0; y < len(mat[y]); x++ {
			out[y][x] = uint8(mat[y][x])
		}
	}
	return out
}
