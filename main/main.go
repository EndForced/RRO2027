package main

import (
	"log"
	"os"
	"time"

	tele "gopkg.in/telebot.v4"
)

func main() {
	pref := tele.Settings{
		Token:  os.Getenv("TOKEN"),
		Poller: &tele.LongPoller{Timeout: 10 * time.Second},
	}

	b, err := tele.NewBot(pref)
	if err != nil {
		log.Fatal(err)
		return
	}

	b.Handle("/start", func(c tele.Context) error {
		text := `Привет! Это генератор расстановок для категории будущие инженеры
Сгенерировать: /gen
Решить последнюю расстановку: /solve

Расстановки соответствуют <a href="https://robofinist.ru">регламенту категории</a> на 18.09.26`

		// Обязательно передаем tele.ModeHTML, чтобы Telegram распарсил тег <a>
		return c.Send(text, tele.ModeHTML)
	})

	b.Start()
}
