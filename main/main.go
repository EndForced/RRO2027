package main

import (
	"FE2027/file_operator"
	"FE2027/generatorHandler"
	"FE2027/matrixgenerator"
	"fmt"
)

const batchSize = 25
const perPatternsAlert = 25

func main() {
	//Кэш повернутых паттернов для генерации
	matrixgenerator.CacheDiredPatterns()
	file_operator.Init()
	fmt.Print("Успешно инициализирован\nНе завершайте программу до конца генерации, это может привести к повреждению файла с паттернами!\n")
	patN, _ := file_operator.GetPatsNumber()
	fmt.Printf("На данный момент в файле сохранено %v паттернов\n", patN)
	var n int
	fmt.Print("Введите количество паттернов для генерации\n")

	_, err := fmt.Scan(&n)
	if err != nil {
		fmt.Println("Ошибка: Вы ввели не число!")
		return
	}

	fmt.Print("Начало генерации...\n")
	totalPatGened := 0

	remaining := n

	for remaining > 0 {
		batchS := batchSize
		if remaining < batchSize {
			batchS = remaining
		}

		batch := generatorHandler.GenerateFullyLegitPatterns(8, batchS)

		for _, element := range batch {
			pat := element.Pattern
			route := element.Route
			file_operator.Insert(pat, route)

			totalPatGened += 1
			remaining -= 1

			if totalPatGened%perPatternsAlert == 0 {
				fmt.Printf("Сгенерировано %v паттернов, %v%% от общего числа\n", totalPatGened, (totalPatGened*100)/n)
			}
		}
	}
	fmt.Print("Генерация закончена\n")

}
