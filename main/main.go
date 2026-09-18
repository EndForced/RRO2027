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
		return c.Send("Бот успешно запущен в безопасном режиме!")
	})

	log.Println("Бот успешно стартовал...")
	b.Start()
}
