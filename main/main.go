package main

import (
	"fmt"
	"log"
	"os"
	"time"

	"github.com/joho/godotenv"
	tele "gopkg.in/telebot.v3"

	"TgPatBot/file_operator"
	"TgPatBot/matrix2image"
	"bytes"
	"image/png"
	"math/rand/v2"
	"sync"
)

func main() {
	err := godotenv.Load()
	file_operator.Init()
	if err != nil {
		log.Fatal("Ошибка загрузки файла .env! Убедитесь, что вы создали его на основе .env.example")
	}

	var (
		cachedIds   = make(map[int64]int)
		cachedIdsMu sync.Mutex
	)

	botToken := os.Getenv("TELEGRAM_BOT_TOKEN")
	if botToken == "" {
		log.Fatal("Переменная TELEGRAM_BOT_TOKEN не найдена в файле .env")
	}

	pref := tele.Settings{
		Token:  botToken,
		Poller: &tele.LongPoller{Timeout: 10 * time.Second},
	}

	b, err := tele.NewBot(pref)
	if err != nil {
		log.Fatal(err)
	}

	log.Println("Бот успешно стартовал...")

	b.Handle("/start", func(c tele.Context) error {
		text := `Привет! Это генератор расстановок для категории будущие инженеры
Сгенерировать: /gen
Решить последнюю расстановку: /solve
Расстановки соответствуют <a href="https://robofinist.ru/event/info/competitions/id/1523">регламенту категории</a> на 18.09.26`

		return c.Send(text, tele.ModeHTML)
	})

	b.Handle("/gen", func(c tele.Context) error {
		fmt.Print("Got gen request")
		uId := c.Chat().ID
		totalN, _ := file_operator.GetPatsNumber()
		chosen := rand.N(totalN)

		cachedIdsMu.Lock()
		cachedIds[uId] = chosen
		cachedIdsMu.Unlock()

		pat, _, _ := file_operator.GetNsPat(chosen)
		fmt.Printf("Choosen pat: %v", pat)

		img, _ := matrix2image.Visualize(toUint8(pat))

		var buf bytes.Buffer
		if err := png.Encode(&buf, img); err != nil {
			return err
		}

		photo := &tele.Photo{
			File: tele.FromReader(&buf),
		}
		return c.Send(photo)
	})

	b.Handle("/solve", func(c tele.Context) error {
		uId := c.Chat().ID
		cachedIdsMu.Lock()
		id, ok := cachedIds[uId]
		cachedIdsMu.Unlock()
		if !ok {
			return c.Send("Произошла неожиданная ошибка")
		}
		pat, route, _ := file_operator.GetNsPat(id)
		img, _ := matrix2image.Visualize(toUint8(pat))
		matrix2image.DrawRoutes(route, img)
		var buf bytes.Buffer
		if err := png.Encode(&buf, img); err != nil {
			return err
		}
		photo := &tele.Photo{
			File: tele.FromReader(&buf),
		}
		return c.Send(photo)

	})
	b.Start()
}

func toUint8(in [][]int) [][]uint8 {
	out := make([][]uint8, len(in))
	for i, row := range in {
		out[i] = make([]uint8, len(row))
		for j, v := range row {
			out[i][j] = uint8(v)
		}
	}
	return out
}
