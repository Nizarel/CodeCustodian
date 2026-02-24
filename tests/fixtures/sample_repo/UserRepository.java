// Multi-language scanner fixture — Java
// Tests: TODO detection, hardcoded secrets, SQL injection, command injection, weak crypto

package com.example;

import java.sql.Connection;
import java.sql.Statement;
import java.security.MessageDigest;

// TODO: migrate to Spring Data JPA before production release
// FIXME: remove hardcoded database credentials

public class UserRepository {

    private String password = "admin123!";

    // NOTE: replace with parameterised queries
    public void getUser(Connection conn, String userId) throws Exception {
        Statement stmt = conn.createStatement();
        // HACK: string concat in query — security review pending
        stmt.executeQuery("SELECT * FROM users WHERE id = " + userId);
    }

    public byte[] legacyHash(String input) throws Exception {
        // TODO: upgrade to SHA-256
        MessageDigest md = MessageDigest.getInstance("MD5");
        return md.digest(input.getBytes());
    }

    public void runReport(String reportName) throws Exception {
        // FIXME: command injection risk
        Runtime.getRuntime().exec("report-generator " + reportName);
    }
}
