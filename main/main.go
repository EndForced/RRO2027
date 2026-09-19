package main

import (
	"bytes"
	"fmt"
	"image/png"
	"log"
	"math/rand/v2"
	"os"
	"sync"
	"time"

	"github.com/joho/godotenv"
	tele "gopkg.in/telebot.v3"

	"TgPatBot/file_operator"
	"TgPatBot/matrix2image"
)

type User struct {
	Generated int
	Solved    int
}

var (
	cachedIds   = make(map[int64]int)
	cachedIdsMu sync.Mutex

	users   = make(map[int64]*User)
	usersMu sync.Mutex
)

// logf пишет строку с временем, ID чата и текстом запроса.
func logf(c tele.Context, format string, args ...any) {
	log.Printf("[%s] chat=%d user=%s | %s",
		time.Now().Format("2006-01-02 15:04:05"),
		c.Chat().ID,
		c.Sender().Username,
		fmt.Sprintf(format, args...),
	)
}

func getUser(id int64) *User {
	usersMu.Lock()
	defer usersMu.Unlock()
	u, ok := users[id]
	if !ok {
		u = &User{}
		users[id] = u
	}
	return u
}

func main() {
	err := godotenv.Load()
	file_operator.Init()
	matrix2image.Cache_all()
	if err != nil {
		log.Fatal("Ошибка загрузки файла .env! Убедитесь, что вы создали его на основе .env.example")
	}

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
		logf(c, "/start")
		text := `Привет! Это генератор расстановок для категории будущие инженеры
Сгенерировать: /gen
Решить последнюю расстановку: /solve
Статистика: /getStatistic
Расстановки соответствуют <a href="https://robofinist.ru/event/info/competitions/id/1523">регламенту категории</a> на 18.09.26`
		return c.Send(text, tele.ModeHTML)
	})

	b.Handle("/gen", func(c tele.Context) error {
		uId := c.Chat().ID
		logf(c, "/gen")

		totalN, _ := file_operator.GetPatsNumber()
		if totalN <= 0 {
			logf(c, "/gen: нет доступных расстановок")
			return c.Send("Ошибка: нет доступных расстановок")
		}
		chosen := rand.N(totalN)

		cachedIdsMu.Lock()
		cachedIds[uId] = chosen
		cachedIdsMu.Unlock()

		getUser(uId).Generated++
		logf(c, "/gen: выдана расстановка #%d", chosen)

		pat, _, err := file_operator.GetNsPat(chosen)
		if err != nil {
			logf(c, "/gen: GetNsPat(%d) err=%v", chosen, err)
			return c.Send("Ошибка при получении расстановки")
		}

		img, err := matrix2image.Visualize(toUint8(pat))
		if err != nil {
			logf(c, "/gen: Visualize err=%v", err)
			return err
		}

		var buf bytes.Buffer
		if err := png.Encode(&buf, img); err != nil {
			return err
		}
		return c.Send(&tele.Photo{File: tele.FromReader(&buf)})
	})

	b.Handle("/solve", func(c tele.Context) error {
		uId := c.Chat().ID
		logf(c, "/solve")

		cachedIdsMu.Lock()
		id, ok := cachedIds[uId]
		cachedIdsMu.Unlock()
		if !ok {
			logf(c, "/solve: нет сохранённой расстановки")
			return c.Send("Сначала сгенерируйте расстановку через /gen")
		}

		pat, route, err := file_operator.GetNsPat(id)
		if err != nil {
			logf(c, "/solve: GetNsPat(%d) err=%v", id, err)
			return c.Send("Ошибка при получении расстановки")
		}

		img, err := matrix2image.Visualize(toUint8(pat))
		if err != nil {
			logf(c, "/solve: Visualize err=%v", err)
			return err
		}
		matrix2image.DrawRoutes(route, img)

		getUser(uId).Solved++
		logf(c, "/solve: решение расстановки #%d", id)

		var buf bytes.Buffer
		if err := png.Encode(&buf, img); err != nil {
			return err
		}
		return c.Send(&tele.Photo{File: tele.FromReader(&buf)})
	})

	b.Handle("/getStatistic", func(c tele.Context) error {
		logf(c, "/getStatistic")

		usersMu.Lock()
		defer usersMu.Unlock()

		if len(users) == 0 {
			return c.Send("Статистика пока пуста.")
		}

		var sb bytes.Buffer
		sb.WriteString("📊 Статистика по пользователям:\n\n")
		for id, u := range users {
			fmt.Fprintf(&sb, "ID %d: сгенерировано %d, решено %d\n", id, u.Generated, u.Solved)
		}
		return c.Send(sb.String())
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
