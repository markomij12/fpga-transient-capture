module adc_spi_tb #(
    parameter int CLKS_PER_SCLK      = 2,
    parameter int SAMPLE_PERIOD_CLKS = 40
) (
    input  logic        clk,
    input  logic        rst,
    input  logic        enable,
    input  logic [11:0] analog_code,
    output logic        cs_n,
    output logic        sclk,
    output logic [11:0] sample,
    output logic        sample_valid
);

    logic sdata;

    adc_spi #(
        .CLKS_PER_SCLK(CLKS_PER_SCLK),
        .SAMPLE_PERIOD_CLKS(SAMPLE_PERIOD_CLKS)
    ) dut (
        .clk(clk),
        .rst(rst),
        .enable(enable),
        .cs_n(cs_n),
        .sclk(sclk),
        .sdata(sdata),
        .sample(sample),
        .sample_valid(sample_valid)
    );

    adc_ad7476a_model model (
        .cs_n(cs_n),
        .sclk(sclk),
        .sdata(sdata),
        .analog_code(analog_code)
    );

endmodule
