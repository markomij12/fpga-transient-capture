// Sim-only capture path: ADC model -> SPI -> trigger/buffer -> UART dump.
// Host CT commands on rx (SET_THRESH / ARM). analog_code stays a TB pin.
// Threshold comes only from host_cmd (default 0x800). Not a board top.
module capture_sim_top #(
    parameter int DEPTH              = 32,
    parameter int WIDTH              = 12,
    parameter int PRE_TRIGGER        = 8,
    parameter int HYSTERESIS         = 4,
    parameter int CLKS_PER_BIT       = 8,
    parameter int CLKS_PER_SCLK      = 2,
    parameter int SAMPLE_PERIOD_CLKS = 40
) (
    input  logic        clk,
    input  logic        rst,
    input  logic        arm,
    input  logic        rx,
    input  logic [11:0] analog_code,
    output logic [1:0]  status,
    output logic        capture_ready,
    output logic        dump_done,
    output logic        tx
);

    logic        enable;
    logic        cs_n;
    logic        sclk;
    logic        sdata;
    logic [11:0] sample;
    logic        sample_valid;
    logic        ready_d;
    logic        dump_start;
    logic [$clog2(DEPTH)-1:0] rd_addr;
    logic [$clog2(DEPTH)-1:0] oldest_addr;
    logic [WIDTH-1:0]         rd_data;
    logic        dump_busy;
    logic        rx_valid;
    logic [7:0]  rx_data;
    logic        arm_pulse;
    logic [11:0] threshold;
    logic        cmd_error;
    logic        arm_or;

    assign enable = 1'b1;
    assign arm_or = arm | arm_pulse;

    uart_rx #(
        .CLKS_PER_BIT(CLKS_PER_BIT)
    ) u_rx (
        .clk     (clk),
        .rst     (rst),
        .rx      (rx),
        .rx_valid(rx_valid),
        .rx_data (rx_data)
    );

    host_cmd u_cmd (
        .clk      (clk),
        .rst      (rst),
        .rx_valid (rx_valid),
        .rx_data  (rx_data),
        .arm_pulse(arm_pulse),
        .threshold(threshold),
        .cmd_error(cmd_error)
    );

    adc_spi #(
        .CLKS_PER_SCLK     (CLKS_PER_SCLK),
        .SAMPLE_PERIOD_CLKS(SAMPLE_PERIOD_CLKS)
    ) u_adc (
        .clk         (clk),
        .rst         (rst),
        .enable      (enable),
        .cs_n        (cs_n),
        .sclk        (sclk),
        .sdata       (sdata),
        .sample      (sample),
        .sample_valid(sample_valid)
    );

    adc_ad7476a_model u_adc_model (
        .cs_n       (cs_n),
        .sclk       (sclk),
        .sdata      (sdata),
        .analog_code(analog_code)
    );

    capture_ctrl #(
        .DEPTH      (DEPTH),
        .WIDTH      (WIDTH),
        .PRE_TRIGGER(PRE_TRIGGER),
        .HYSTERESIS (HYSTERESIS)
    ) u_cap (
        .clk          (clk),
        .rst          (rst),
        .arm          (arm_or),
        .sample_valid (sample_valid),
        .sample       (sample),
        .threshold    (threshold),
        .status       (status),
        .capture_ready(capture_ready),
        .oldest_addr  (oldest_addr),
        .rd_addr      (rd_addr),
        .rd_data      (rd_data)
    );

    uart_dump #(
        .DEPTH       (DEPTH),
        .WIDTH       (WIDTH),
        .PRE_TRIGGER (PRE_TRIGGER),
        .CLKS_PER_BIT(CLKS_PER_BIT)
    ) u_dump (
        .clk        (clk),
        .rst        (rst),
        .start      (dump_start),
        .rd_data    (rd_data),
        .oldest_addr(oldest_addr),
        .rd_addr    (rd_addr),
        .tx         (tx),
        .busy       (dump_busy),
        .done       (dump_done)
    );

    always_ff @(posedge clk) begin
        if (rst) begin
            ready_d     <= 1'b0;
            dump_start  <= 1'b0;
        end else begin
            ready_d    <= capture_ready;
            dump_start <= capture_ready & ~ready_d;
        end
    end

endmodule
