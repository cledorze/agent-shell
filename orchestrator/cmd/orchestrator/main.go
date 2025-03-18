package main

import (
"fmt"
"log"
"net/http"
)

func main() {
log.Println("Starting Orchestrator service...")
http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
fmt.Fprintf(w, "{\"status\":\"healthy\"}")
})
log.Fatal(http.ListenAndServe(":8081", nil))
}
