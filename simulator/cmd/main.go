// Симулятор: go run ./simulator/cmd, затем открыть http://localhost:8080
package main

import (
	"FE2027/file_operator"
	"FE2027/simulator"
	"flag"
	"log"
	"net/http"
	"os"
)

func main() {
	addr := flag.String("addr", "127.0.0.1:8080", "адрес HTTP API и окна симулятора")
	root := flag.String("root", ".", "корень репозитория (там лежат data/pats.bin и matrix2image/assets)")
	flag.Parse()

	if err := os.Chdir(*root); err != nil {
		log.Fatal(err)
	}
	if err := file_operator.Init(); err != nil {
		log.Fatal(err)
	}
	srv, err := simulator.NewServer("matrix2image/assets")
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("Симулятор запущен: http://%s", *addr)
	log.Fatal(http.ListenAndServe(*addr, srv.Handler()))
}
