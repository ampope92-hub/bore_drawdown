// Drawdown rate and licence projection for a coastal monitoring bore.
//
// The compliance logger samples every 12 hours, and the bore sits 300 m from an estuary, so it
// breathes with the tide. The semidiurnal tide has a period of 12.42 hours, which is longer than
// the logger interval by 25 minutes: each sample lands a little later in the tidal cycle than
// the one before, and the logger records the tide folded down to a slow swing of about 15 days
// and a fifth of a metre. Over an abstraction period of a couple of weeks that swing looks like
// a trend, and a straight line through the samples reads it as one. The tide is a known signal
// with a known period, so it is fitted alongside the trend at the actual sample times, where
// it is exactly the aliased swing the logger recorded, and the trend that remains is the
// drawdown. The commissioning dump at ten-minute resolution shows the period directly, so it
// is measured there rather than assumed.
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public class Drawdown {

    static final class Sample {
        final LocalDateTime t;
        final double depth;
        Sample(LocalDateTime t, double depth) { this.t = t; this.depth = depth; }
    }

    static List<Sample> readSeries(Path path) throws IOException {
        List<Sample> out = new ArrayList<>();
        try (BufferedReader in = new BufferedReader(new FileReader(path.toFile()))) {
            String line;
            boolean header = true;
            while ((line = in.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty()) continue;
                if (header) { header = false; continue; }
                String[] f = line.split(",");
                out.add(new Sample(LocalDateTime.parse(f[0].trim()), Double.parseDouble(f[1].trim())));
            }
        }
        return out;
    }

    /** A tiny JSON reader for the flat bore.json: key -> raw value text. */
    static String jsonField(String text, String key) {
        int k = text.indexOf("\"" + key + "\"");
        if (k < 0) throw new IllegalArgumentException("bore.json has no " + key);
        int colon = text.indexOf(':', k);
        int end = colon + 1;
        while (end < text.length() && ",}".indexOf(text.charAt(end)) < 0) end++;
        return text.substring(colon + 1, end).trim().replace("\"", "");
    }

    /** Least squares by normal equations with partial pivoting; the systems here are 4 by 4. */
    static double[] leastSquares(double[][] x, double[] y) {
        int n = x.length, p = x[0].length;
        double[][] a = new double[p][p + 1];
        for (int i = 0; i < n; i++)
            for (int j = 0; j < p; j++) {
                for (int k = 0; k < p; k++) a[j][k] += x[i][j] * x[i][k];
                a[j][p] += x[i][j] * y[i];
            }
        // A sampling interval that lands a whole number of times in the tidal period leaves one of
        // the sine or cosine columns proportional to the intercept, and the system is then
        // singular. Ridging the diagonal by a hair keeps the solve finite and returns the
        // minimum-norm answer instead of dividing by a pivot of zero; on a well conditioned
        // system the shift is far below the noise and changes no reported figure.
        double scale = 0.0;
        for (int j = 0; j < p; j++) scale = Math.max(scale, Math.abs(a[j][j]));
        if (scale == 0.0) scale = 1.0;
        for (int j = 0; j < p; j++) a[j][j] += 1e-12 * scale;
        for (int c = 0; c < p; c++) {
            int piv = c;
            for (int r = c + 1; r < p; r++) if (Math.abs(a[r][c]) > Math.abs(a[piv][c])) piv = r;
            double[] tmp = a[c]; a[c] = a[piv]; a[piv] = tmp;
            if (Math.abs(a[c][c]) < 1e-30 * scale) a[c][c] = (a[c][c] < 0 ? -1 : 1) * 1e-30 * scale;
            for (int r = c + 1; r < p; r++) {
                double f = a[r][c] / a[c][c];
                for (int k = c; k <= p; k++) a[r][k] -= f * a[c][k];
            }
        }
        double[] b = new double[p];
        for (int c = p - 1; c >= 0; c--) {
            double s = a[c][p];
            for (int k = c + 1; k < p; k++) s -= a[c][k] * b[k];
            b[c] = s / a[c][c];
        }
        return b;
    }

    static double hours(LocalDateTime from, LocalDateTime t) {
        return ChronoUnit.SECONDS.between(from, t) / 3600.0;
    }

    /** Residual sum of squares of level + one sinusoid of period T hours, no trend: the
     *  commissioning dump was taken with the pump off. */
    static double rss(List<Sample> s, LocalDateTime origin, double periodH) {
        int n = s.size();
        double[][] x = new double[n][3];
        double[] y = new double[n];
        for (int i = 0; i < n; i++) {
            double w = 2 * Math.PI * hours(origin, s.get(i).t) / periodH;
            x[i][0] = 1; x[i][1] = Math.cos(w); x[i][2] = Math.sin(w);
            y[i] = s.get(i).depth;
        }
        double[] b = leastSquares(x, y);
        double r = 0;
        for (int i = 0; i < n; i++) {
            double e = y[i] - (b[0] + b[1] * x[i][1] + b[2] * x[i][2]);
            r += e * e;
        }
        return r;
    }

    // The mean of the fitted level over the 24 hours that begin at dayStart, at the ten minute step
    // the compliance logger runs at. The tidal term is evaluated at each step's own time and carried
    // into the mean, because a day is not a whole number of tidal cycles.
    static double dayMean(double[] b, double period, LocalDateTime origin,
                          LocalDateTime dayStart, LocalDateTime pumpStart) {
        double sum = 0;
        for (int i = 0; i < 144; i++) {
            LocalDateTime t = dayStart.plusMinutes(10L * i);
            double w = 2 * Math.PI * hours(origin, t) / period;
            sum += b[0] + b[1] * pumpDays(t, pumpStart) + b[2] * Math.cos(w) + b[3] * Math.sin(w);
        }
        return sum / 144.0;
    }

    static double pumpDays(LocalDateTime t, LocalDateTime pumpStart) {
        double d = ChronoUnit.SECONDS.between(pumpStart, t) / 86400.0;
        return d > 0 ? d : 0;
    }

    public static void main(String[] args) throws IOException {
        if (args.length != 2) {
            System.err.println("usage: Drawdown <data-dir> <output-json>");
            System.exit(2);
        }
        Path data = Path.of(args[0]);
        String meta = Files.readString(data.resolve("bore.json"));
        LocalDateTime pumpStart = LocalDateTime.parse(jsonField(meta, "abstraction_start"));
        double limit = Double.parseDouble(jsonField(meta, "licence_limit_mm_per_day"));
        double intake = Double.parseDouble(jsonField(meta, "pump_intake_depth_m"));
        double horizon = Double.parseDouble(jsonField(meta, "projection_day"));
        // The measuring point moved off the casing top part way through the record, and the export
        // is written as measured from wherever the point was. The licence, the intake depth and the
        // regulator's record are all depth below the casing top, so every reading taken from the
        // stamp on is brought back onto that datum by the offset bore.json gives.
        LocalDateTime moved = LocalDateTime.parse(jsonField(meta, "measuring_point_moved_at"));
        double offset = Double.parseDouble(jsonField(meta, "measuring_point_offset_m"));

        // The tidal period, read off the commissioning dump: the period that best explains the
        // ten-minute samples taken before the pump went to work. The bore is on a semidiurnal
        // tide, which the README puts between 10 and 15 hours, so that is the range searched. The
        // figure itself is still measured off this bore's own dump rather than written in here,
        // because every bore breathes at its own period somewhere in that band.
        List<Sample> hires = readSeries(data.resolve("commissioning_10min.csv"));
        double loT = 10.0, hiT = 15.0;
        double bestT = loT, bestR = Double.MAX_VALUE;
        for (double T = loT; T <= hiT; T += 0.002) {
            double r = rss(hires, hires.get(0).t, T);
            if (r < bestR) { bestR = r; bestT = T; }
        }
        // Refine around the coarse winner. A period error rides the tidal amplitude: the phase it
        // loses across the record shows up in the fitted level multiplied by how far the bore
        // swings, so on a bore that breathes hard the coarse grid alone is not close enough.
        double lo = bestT - 0.002, hi = bestT + 0.002;
        for (double T = lo; T <= hi; T += 0.00002) {
            double r = rss(hires, hires.get(0).t, T);
            if (r < bestR) { bestR = r; bestT = T; }
        }

        // The compliance series: level, drawdown per day of abstraction, and the tide evaluated
        // at each sample's own time. Samples before abstraction pin the tide and the base level.
        List<Sample> s = readSeries(data.resolve("levels.csv"));
        LocalDateTime origin = s.get(0).t;
        int n = s.size();
        double[][] x = new double[n][4];
        double[] y = new double[n];
        for (int i = 0; i < n; i++) {
            double w = 2 * Math.PI * hours(origin, s.get(i).t) / bestT;
            x[i][0] = 1; x[i][1] = pumpDays(s.get(i).t, pumpStart); x[i][2] = Math.cos(w); x[i][3] = Math.sin(w);
            y[i] = s.get(i).depth - (s.get(i).t.isBefore(moved) ? 0.0 : offset);
        }
        double[] b = leastSquares(x, y);
        // A day's figure is the mean of the level over that day, taken the way the regulator takes
        // it: the 24 hours from the time of day the abstraction began, averaged over ten minute
        // steps. The tide does not drop out of that average. Its period is 12.42 h, which does not
        // divide 24, so a whole day of it leaves a small residue that shifts from day to day as the
        // tide walks against the clock, and the fitted tidal term has to be carried into the mean
        // rather than discarded. Reporting the trend alone is what the old return did.
        LocalDateTime projDay = pumpStart.plusSeconds(Math.round(horizon * 86400.0));
        double depthStart = dayMean(b, bestT, origin, pumpStart, pumpStart);
        double projected = dayMean(b, bestT, origin, projDay, pumpStart);
        double rateMmDay = 1000.0 * (projected - depthStart) / horizon;
        boolean within = rateMmDay <= limit && projected < intake;

        // One day's mean for every day of the abstraction period in the record.
        // The record runs to the last calendar day it holds a reading on, and the report covers every
        // day of the abstraction up to that one. The last reading can fall earlier in the day than
        // abstraction began, so the comparison is on the date and not on the timestamp.
        LocalDate lastDay = s.get(n - 1).t.toLocalDate();
        StringBuilder daily = new StringBuilder();
        for (LocalDateTime day = pumpStart; !day.toLocalDate().isAfter(lastDay); day = day.plusDays(1)) {
            if (daily.length() > 0) daily.append(',');
            daily.append(String.format(Locale.ROOT, "\"%s\":%.3f",
                    day.toLocalDate(), dayMean(b, bestT, origin, day, pumpStart)));
        }

        File outFile = new File(args[1]);
        if (outFile.getParentFile() != null) outFile.getParentFile().mkdirs();
        try (PrintWriter out = new PrintWriter(new FileWriter(outFile))) {
            out.printf(Locale.ROOT,
                    "{\"daily_depth_m\":{%s},\"projected_depth_m\":%.3f,\"drawdown_mm_per_day\":%.4f,"
                    + "\"tidal_period_h\":%.4f,\"within_licence\":%s}%n",
                    daily, projected, rateMmDay, bestT, within ? "true" : "false");
        }
        System.err.printf(Locale.ROOT, "tidal period %.3f h, drawdown %.2f mm/day, projected %.3f m%n", bestT, rateMmDay, projected);
    }
}
