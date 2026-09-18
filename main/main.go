package main

import (
	"fmt"
	"log"
	"os"
	"time"

	"github.com/joho/godotenv"
	tele "gopkg.in/telebot.v3"
)

func main() {
	err := godotenv.Load()
	if err != nil {
		log.Fatal("Ошибка загрузки файла .env! Убедитесь, что вы создали его на основе .env.example")
	}

	botToken := os.Getenv("TELEGRAM_BOT_TOKEN")
	if botToken == "" {
		log.Fatal("Переменная TELEGRAM_BOT_TOKEN не найдена в файле .env")
	}

	fmt.Print(botToken)

	pref := tele.Settings{
		Token:  botToken,
		Poller: &tele.LongPoller{Timeout: 10 * time.Second},
	}

	b, err := tele.NewBot(pref)
	if err != nil {
		log.Fatal(err)
	}

	b.Handle("/start", func(c tele.Context) error {
		text := `Привет! Это генератор расстановок для категории будущие инженеры
Сгенерировать: /gen
Решить последнюю расстановку: /solve
Расстановки соответствуют <a href="https://robofinist.ru/event/info/competitions/id/1523">регламенту категории</a> на 18.09.26`

		// Обязательно передаем tele.ModeHTML, чтобы Telegram распарсил тег <a>
		return c.Send(text, tele.ModeHTML)
	})

	log.Println("Бот успешно стартовал...")
	b.Start()
}
