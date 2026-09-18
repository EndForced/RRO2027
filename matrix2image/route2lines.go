package matrix2image

import (
	"fmt"
	"image"
	"image/color"
)

//flat indexing is implemented
// idx = y * n + x where n is pic size
//Да, тут не самый чистый код и есть костыли и захардкоденные значения
//Но у этой штуки не такой уж и важный фунционал
//Да и код тут не такой уж и плохой

func calculateOffset(idx int) int {
	// idx % 10 делит пути на циклы по 10 штук
	if idx%10 < 5 {
		// Первые 5 путей цикла (0, 1, 2, 3, 4) идут вперед
		return 8 * (idx%5 + 1)
	}
	// Следующие 5 путей цикла (5, 6, 7, 8, 9) идут в обратную сторону
	return 8 * (6 - idx%5)
}

func DrawRoutes(routes [][]int, img *image.RGBA) error {
	var err error
	for idx, route := range routes {
		offset := calculateOffset(idx)
		for cellIDX := range len(route) - 1 {
			p1, _ := getRightBottomCorner(route[cellIDX], img)
			p2, _ := getRightBottomCorner(route[cellIDX+1], img)

			x1, y1 := p1.X, p1.Y
			x2, y2 := p2.X, p2.Y
			fp1 := image.Point{X: x1 - offset, Y: y1 - offset}
			fp2 := image.Point{X: x2 - offset, Y: y2 - offset}
			err = DrawStraightLine(img, fp1, fp2, 8, getRGBAColor(idx))
			if err != nil {
				return err
			}
		}
	}

	return nil
}

func getRightBottomCorner(id int, img *image.RGBA) (image.Point, error) {
	size := (img.Bounds().Max.Y + 1) / 100
	y, x := id/size, id%size
	if !(y < size && x < size) {
		return image.Point{}, fmt.Errorf("Can't return corner out of bounds\nIDX: %v", id)
	}
	return image.Point{
			X: 100 * (x + 1),
			Y: 100 * (y + 1),
		},
		nil
}

func DrawStraightLine(img *image.RGBA, p1 image.Point, p2 image.Point, thickness int, color color.Color) error {
	dx := p2.X - p1.X
	dy := p2.Y - p1.Y
	mDims := img.Bounds()

	if dx != 0 && dy != 0 {
		return fmt.Errorf("Can't draw non horizontal / vertical line with points \n%v, %v", p1, p2)
	}

	if thickness < 1 {
		thickness = 1
	}

	isVertical := dx == 0

	if p1.X > p2.X {
		p1.X, p2.X = p2.X, p1.X
	}
	if p1.Y > p2.Y {
		p1.Y, p2.Y = p2.Y, p1.Y
	}

	offset1 := thickness / 2
	offset2 := thickness - offset1

	if isVertical {
		p1.Y -= offset1
		p2.Y += offset2 - 1

		for x := p1.X - offset1; x < p1.X-offset1+thickness; x++ {
			for y := p1.Y; y <= p2.Y; y++ {
				if (image.Point{X: x, Y: y}.In(mDims)) {
					img.Set(x, y, color)
				}
			}
		}

	} else {
		p1.X -= offset1
		p2.X += offset2 - 1

		for y := p1.Y - offset1; y < p1.Y-offset1+thickness; y++ {
			for x := p1.X; x <= p2.X; x++ {
				if (image.Point{X: x, Y: y}.In(mDims)) {
					img.Set(x, y, color)
				}
			}
		}
	}

	return nil
}
