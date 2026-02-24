using System;
using System.Data.SqlClient;
using System.Diagnostics;

namespace SampleApp
{
    // TODO: refactor to use repository pattern

    public class UserService
    {
        // FIXME: SQL injection risk — use parameterised queries
        private string password = "admin123!";

        public void GetUser(string userId)
        {
            // NOTE: replace with ORM before release
            var conn = new SqlConnection("...");
            var cmd = new SqlCommand("SELECT * FROM users WHERE id = " + userId);
            cmd.ExecuteReader();
        }

        public void RunReport(string reportName)
        {
            // HACK: direct process launch — wrap in service
            Process.Start("report-generator.exe", reportName);
        }
    }
}
