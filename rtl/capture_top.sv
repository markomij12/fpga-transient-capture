// Synthesizable capture top: SPI ADC, trigger/buffer, UART dump + CT commands.
// No ADC model, no XDC, no board LED names.
// arm_btn: 2-FF sync + rising-edge pulse, OR with UART arm_pulse.
// Dump starts on capture_ready rising edge, not on arm.
module capture_top #(
    parameter int DEPTH              = 2048,
    parameter int WIDTH              = 12,
    parameter int PRE_TRIGGER        = 512,
    parameter int HYSTERESIS         = 16,
    parameter int CLKS_PER_BIT       = 868,
    parameter int CLKS_PER_SCLK      = 5,
    parameter int SAMPLE_PERIOD_CLKS = 100
) (
    input  logic        clk,
    input  logic        rst,
    input  logic        uart_rx,
    output logic        uart_tx,
    output logic        adc_cs_n,
    output logic        adc_sclk,
    input  logic        adc_sdata,
    input  logic        arm_btn,
    output logic [1:0]  status
);

    logic        enable;
    logic [11:0] sample;
    logic        sample_valid;
    logic        capture_ready;
    logic        ready_d;
    logic        dump_start;
    logic        dump_busy;
    logic        dump_done;
    logic [$clog2(DEPTH)-1:0] rd_addr;
    logic [$clog2(DEPTH)-1:0] oldest_addr;
    logic [WIDTH-1:0]         rd_data;
    logic        rx_valid;
    logic [7:0]  rx_data;
    logic        arm_pulse;
    logic [11:0] threshold;
    logic        cmd_error;
    logic        arm_btn_m;
    logic        arm_btn_s;
    logic        arm_btn_d;
    logic        arm_btn_pulse;
    logic        arm_or;

    assign enable        = 1'b1;
    assign arm_btn_pulse = arm_btn_s & ~arm_btn_d;
    assign arm_or        = arm_btn_pulse | arm_pulse;

    always_ff @(posedge clk) begin
        if (rst) begin
            arm_btn_m <= 1'b0;
            arm_btn_s <= 1'b0;
            arm_btn_d <= 1'b0;
        end else begin
            arm_btn_m <= arm_btn;
            arm_btn_s <= arm_btn_m;
            arm_btn_d <= arm_btn_s;
        end
    end

    uart_rx #(
        .CLKS_PER_BIT(CLKS_PER_BIT)
    ) u_rx (
        .clk     (clk),
        .rst     (rst),
        .rx      (uart_rx),
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
        .cs_n        (adc_cs_n),
        .sclk        (adc_sclk),
        .sdata       (adc_sdata),
        .sample      (sample),
        .sample_valid(sample_valid)
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
        .tx         (uart_tx),
        .busy       (dump_busy),
        .done       (dump_done)
    );

    always_ff @(posedge clk) begin
        if (rst) begin
            ready_d    <= 1'b0;
            dump_start <= 1'b0;
        end else begin
            ready_d    <= capture_ready;
            dump_start <= capture_ready & ~ready_d;
        end
    end

endmodule
