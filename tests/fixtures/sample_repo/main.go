package main

import (
	"database/sql"
	"fmt"
	"os/exec"
)

// TODO: migrate authentication to OAuth before production release
// FIXME: remove hardcoded credentials

const apiSecret = "AKIAIOSFODNN7EXAMPLE"

func getUserData(db *sql.DB, userID string) {
	// TODO: add input validation here
	query := "SELECT * FROM users WHERE id = " + userID
	db.Query(query + userID)
}

func runBackup(target string) {
	// HACK: using direct exec — replace with proper backup library
	exec.Command("tar", "-czf", target, "/data")
}

func main() {
	fmt.Println("CodeCustodian multi-lang fixture")
}
